"""📈 资金路线 · AI研判 Tab

主线板块资金路线推演 + 多风格大V AI分析
"""
import tkinter as _tk
import tkinter.ttk as _ttk
import tkinter.scrolledtext as _st
import threading as _th
import time as _time
import datetime as _dt

_BG = "#1A1A2E"; _PANEL = "#16213E"; _CARD = "#0F3460"; _FG = "#EAEAEA"
_MUTED = "#90A4AE"; _ACCENT = "#E94560"; _GOLD = "#FFD54F"; _GREEN = "#66BB6A"
_BLUE = "#64B5F6"; _PURPLE = "#AB47BC"

# ═══════════════════════════════════════════════════════
# 🎭 大V风格 prompt 库
# ═══════════════════════════════════════════════════════
STYLES = [
    {
        "id": "default", "name": "🤖 综合研判", "icon": "📊",
        "color": _BLUE,
        "system": "你是专业的A股交易分析师，融合技术面、资金面、情绪周期、筹码结构、政策驱动、外围影响（美股/汇率）和财经日历事件进行综合研判。输出中文，结构清晰。",
        "intro": "【综合研判 · 多维度交叉验证】",
    },
    {
        "id": "ji Fang", "name": "简放", "icon": "📚",
        "color": "#26A69A",
        "system": "你是简放风格的A股价值投资分析师。核心理念：「在认知能力内做大概率正确的事」「用时间换空间」「估值+成长」。强调：① 赛道级产业逻辑（不做纯题材）；② 业绩确定性+估值安全边际；③ 机构博弈（北向/基金/社保/QFII动向）；④ 长期持股心态建设。语气务实、不追热点。",
        "intro": "【简放风格 · 估值锚 + 机构资金】",
    },
    {
        "id": "xiaoqun", "name": "陈小群", "icon": "⚡",
        "color": _ACCENT,
        "system": "你是陈小群风格的A股游资分析师。核心理念：情绪周期+龙头战法，只做主线只做总龙拒绝杂毛。情绪周期分4阶段（冰点试错→主升发酵→高潮一致→退潮主跌），每阶段配不同仓位。强调：① 情绪周期定仓位；② 主线总龙识别（板块≥5只涨停+辨识度最高）；③ 龙头首阴反包是行情延续信号；④ 高潮一致阶段只卖不买。",
        "intro": "【陈小群风格 · 情绪周期 · 只做总龙】",
    },
    {
        "id": "zhao_lao_ge", "name": "赵老哥", "icon": "🔥",
        "color": _GOLD,
        "system": "你是赵老哥风格的A股游资分析师。核心理念：「十年一梦，一场游戏一场梦」「只做强势，连板优先，量能配合」「题材为王，龙头先行」。强调：① 连板数≥3的强势股才有参与价值；② 量能是真突破的基础（倍量/放量过前高）；③ 板块联动效应（至少3只同题材涨停）；④ 不预测只跟随，市场永远是对的。",
        "intro": "【赵老哥风格 · 连板龙头 · 量价为王】",
    },
    {
        "id": "feng_liu", "name": "冯柳", "icon": "🎯",
        "color": "#FF7043",
        "system": "你是冯柳风格的A股逆向投资分析师。核心理念：「弱者体系」——「赚市场错杀的钱」「在不确定中寻找确定」「利用赔率覆盖胜率」。强调：① 大幅下跌后逻辑未被破坏的公司；② 市场一致悲观时才敢重仓；③ 接受小概率事件发生但赔率足够；④ 不做左侧，不接飞刀，等第一个季报验证。",
        "intro": "【冯柳风格 · 弱者体系 · 逆向赔率】",
    },
    {
        "id": "duanyongping", "name": "段永平", "icon": "💎",
        "color": "#8D6E63",
        "system": "你是段永平风格的A股价值投资分析师。核心理念：「买股票就是买公司的一部分」「长期持有看得懂的生意」「安全边际+好管理层+好文化」。7维打分：商业模式、盈利质量、成长性、现金流、安全边际、护城河、估值。10年以上视角，不关心短期波动，只关心企业价值。",
        "intro": "【段永平风格 · 价值投资 · 10年视角】",
    },
    {
        "id": "guojia_dui", "name": "国家队·主力", "icon": "🏛️",
        "color": "#7E57C2",
        "system": "你是国家队/主力资金视角的A股分析师。关注：① 外资（北向资金/Lof）动向；② 社保/险资/汇金持仓变化；③ 量化私募规模（3万亿+）对小微盘的冲击；④ 中证ETF/沪深300ETF异常申赎；⑤ 关键位置护盘信号（3000点/3200点整数关口）；⑥ 板块建仓/换筹/出货的筹码结构演变。",
        "intro": "【国家队视角 · 大资金 · 筹码推演】",
    },
]


# ═══════════════════════════════════════════════════════
# 📦 数据层：从实时行情聚合板块资金路线
# ═══════════════════════════════════════════════════════
_CACHE = {"route": (None, 0.0), "route_week": (None, 0.0)}
_CACHE_TTL = 120


def _get_mainline_route_data():
    """
    拉取并聚合板块轮动 + 资金路线数据
    返回 dict:
      sectors: [(板块, 今日涨跌幅%, 成交额亿, 领涨股, 领涨股涨跌%, 涨跌家数比, 涨停数), ...]
      hot_themes: [近期热门概念]
      macro: {美股近1天涨跌, 美元指数, 汇率, ...}  (如果能拉)
      date_str: 当前交易日期字符串
    """
    now = _time.time()
    cached, ts = _CACHE["route"]
    if cached and (now - ts) < _CACHE_TTL:
        return cached

    result = {
        "sectors": [],
        "hot_themes": [],
        "macro": {},
        "date_str": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    try:
        import akshare as _ak
        import pandas as _pd

        # ① 同花顺行业板块汇总（90 个行业）
        try:
            df = _ak.stock_board_industry_summary_ths()
            if df is not None and not df.empty:
                df["涨跌幅"] = _pd.to_numeric(df["涨跌幅"], errors="coerce")
                top10 = df.nlargest(10, "涨跌幅")
                for _, r in top10.iterrows():
                    up_down = ""
                    try:
                        up_n = int(r.get("上涨家数", 0)); dn_n = int(r.get("下跌家数", 0))
                        up_down = f"{up_n}/{dn_n}" if (up_n or dn_n) else ""
                    except Exception:
                        pass
                    result["sectors"].append((
                        str(r.get("板块", "")),
                        round(float(r.get("涨跌幅", 0)), 2),
                        round(float(r.get("总成交额", 0)), 1),
                        str(r.get("领涨股", "")),
                        round(float(r.get("领涨股-涨跌幅", 0)), 2),
                        up_down,
                    ))
        except Exception as e:
            print(f"[📈路线❌] 行业板块失败: {e}")

        # ② 同花顺概念板块 Top 热点（容错秒跳过）
        try:
            cdf = _ak.stock_board_concept_summary_ths()
            if cdf is not None and not cdf.empty:
                cdf["涨跌幅"] = _pd.to_numeric(cdf["涨跌幅"], errors="coerce")
                for _, r in cdf.nlargest(8, "涨跌幅").iterrows():
                    result["hot_themes"].append((
                        str(r.get("板块", "")),
                        round(float(r.get("涨跌幅", 0)), 2),
                    ))
        except Exception as e:
            # bs4 版本不够时跳过, 不打印 (太吵)
            if "bs4" not in str(e).lower():
                print(f"[📈路线] 概念板块跳过: {str(e)[:60]}")

        # ③ 宏观快速：纳指/美元（新浪）
        try:
            try:
                ndf = _ak.index_us_stock_sina(symbol=".IXIC")
                if ndf is not None and not ndf.empty:
                    last_chg = _pd.to_numeric(ndf["涨跌幅"], errors="coerce")
                    result["macro"]["纳指(昨)"] = f"{float(last_chg.iloc[-1]):+.2f}%" if len(last_chg) > 0 else "-"
            except Exception:
                result["macro"]["纳指"] = "-"
        except Exception:
            pass

    except Exception as e:
        print(f"[📈路线❌] 顶层异常: {e}")

    _CACHE["route"] = (result, _time.time())
    return result


# ═══════════════════════════════════════════════════════
# 🖥️ UI：资金路线 Tab 完整内容
# ═══════════════════════════════════════════════════════
def _build_mainline_route_tab(parent_nb):
    """
    在 parent_nb (ttk.Notebook) 中 add 一个 Tab，返回 tab frame
    """
    tab = _ttk.Frame(parent_nb)
    parent_nb.add(tab, text="  📈 资金路线·AI研判  ")

    # ── 内部用 tk.Frame 包（ttk 不支持 bg） ──
    root = _tk.Frame(tab, bg=_BG)
    root.pack(fill=_tk.BOTH, expand=True)

    # ══════════════════════════════════════════════════
    # ① 顶部：实时数据预览 + 刷新按钮 + 字体/背景调节
    # ══════════════════════════════════════════════════
    top = _tk.Frame(root, bg=_PANEL)
    top.pack(fill=_tk.X, padx=10, pady=(10, 4))

    _tk.Label(top, text="📈  资金路线推演 · AI 多风格研判  ",
              font=("TkDefaultFont", 12, "bold"),
              bg=_PANEL, fg=_GOLD).pack(side=_tk.LEFT, padx=10, pady=6)

    # 实时数据区（顶部一行小卡片）
    data_row = _tk.Frame(root, bg=_BG)
    data_row.pack(fill=_tk.X, padx=10, pady=4)
    data_cards = []

    def _mk_card(title, color):
        f = _tk.Frame(data_row, bg=_PANEL, highlightthickness=1, highlightbackground=color)
        f.pack(side=_tk.LEFT, fill=_tk.X, expand=True, padx=3)
        _tk.Label(f, text=title, bg=_PANEL, fg=_MUTED,
                  font=("TkDefaultFont", 8)).pack(anchor="w", padx=6, pady=(4, 0))
        v = _tk.Label(f, text="--", bg=_PANEL, fg=color,
                      font=("TkDefaultFont", 11, "bold"))
        v.pack(anchor="w", padx=6, pady=(0, 4))
        return v

    card_top_ind = _mk_card("🏭 今日最强行业", _ACCENT)
    card_top_con = _mk_card("🔥 最热概念", _GOLD)
    card_themes = _mk_card("📊 主线板块数", _BLUE)
    card_date = _mk_card("📅 数据时间", _MUTED)

    data_cards.extend([card_top_ind, card_top_con, card_themes, card_date])

    # ══════════════════════════════════════════════════
    # ② 大V风格按钮组（上排）
    # ══════════════════════════════════════════════════
    guru_row = _tk.Frame(root, bg=_BG)
    guru_row.pack(fill=_tk.X, padx=10, pady=(6, 2))

    _tk.Label(guru_row, text="🤖 选择大V风格:", bg=_BG, fg=_MUTED,
              font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=(0, 8))

    active_guru = _tk.StringVar(value="default")
    guru_btns = {}

    def _on_guru_click(gid, btn):
        active_guru.set(gid)
        # 所有按钮恢复白底，当前选中用 color 背景
        for _gid, _b in guru_btns.items():
            _b.config(bg="#FFFFFF", fg="black")
        style = next((s for s in STYLES if s["id"] == gid), None)
        if style:
            btn.config(bg=style["color"], fg="white")
        # 自动触发 AI 分析
        _trigger_ai()

    for style in STYLES:
        btn = _tk.Button(guru_row, text=f"{style['icon']} {style['name']}",
                         width=14,
                         bg="#FFFFFF", fg="black",
                         activebackground="#F5F5F5",
                         highlightbackground=style["color"], highlightthickness=2,
                         font=("TkDefaultFont", 9), cursor="hand2")
        btn.pack(side=_tk.LEFT, padx=2, pady=3)
        guru_btns[style["id"]] = btn
        btn.config(command=lambda gid=style["id"], b=btn: _on_guru_click(gid, b))

    # 默认选中综合研判
    guru_btns["default"].config(bg=STYLES[0]["color"], fg="white")

    # ══════════════════════════════════════════════════
    # ③ 操作按钮 + 状态 + 字体调节
    # ══════════════════════════════════════════════════
    ctrl_row = _tk.Frame(root, bg=_BG)
    ctrl_row.pack(fill=_tk.X, padx=10, pady=2)

    font_size = [11]

    def _fs_up(): font_size[0] = min(22, font_size[0] + 2); _rebuild_text_widget()
    def _fs_dn(): font_size[0] = max(7, font_size[0] - 2); _rebuild_text_widget()
    def _bg_light(): text_widget.config(bg="#FFFFFF", fg="#222", insertbackground="#000")
    def _bg_dark(): text_widget.config(bg=_PANEL, fg=_FG, insertbackground=_FG)
    def _bg_mid(): text_widget.config(bg="#2C3E50", fg="#ECF0F1", insertbackground="#ECF0F1")

    # 主按钮（lambda 延迟绑定，避免闭包顺序问题）
    _tk.Button(ctrl_row, text="🔄 刷新实时数据", width=14,
               command=lambda: _refresh_data(),
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_ACCENT, highlightthickness=2,
               font=("TkDefaultFont", 9, "bold")).pack(side=_tk.LEFT, padx=3)

    _tk.Button(ctrl_row, text="🔍 AI 多风格全分析", width=16,
               command=lambda: _trigger_all_styles(),
               bg=_GOLD, fg="black", activebackground="#F0B429",
               highlightbackground=_ACCENT, highlightthickness=2,
               font=("TkDefaultFont", 9, "bold")).pack(side=_tk.LEFT, padx=3)

    status_lbl = _tk.Label(ctrl_row, text="", bg=_BG, fg=_MUTED,
                           font=("TkDefaultFont", 9))
    status_lbl.pack(side=_tk.LEFT, padx=10)

    # 字体调节
    btn_fs = _tk.Frame(ctrl_row, bg=_BG); btn_fs.pack(side=_tk.RIGHT)
    for t, cmd in [("A+", _fs_up), ("A-", _fs_dn)]:
        _tk.Button(btn_fs, text=t, width=3, command=cmd,
                   bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                   highlightbackground=_BLUE, highlightthickness=1,
                   font=("TkDefaultFont", 9, "bold")).pack(side=_tk.LEFT, padx=1)

    _tk.Label(ctrl_row, text="背景:", bg=_BG, fg=_MUTED,
              font=("TkDefaultFont", 9)).pack(side=_tk.RIGHT, padx=(8, 2))
    bg_btn = _tk.Frame(ctrl_row, bg=_BG); bg_btn.pack(side=_tk.RIGHT)
    for t, cmd, col in [("☀", _bg_light, "#FFFFFF"), ("🌙", _bg_dark, _PANEL), ("🔷", _bg_mid, "#2C3E50")]:
        _tk.Button(bg_btn, text=t, width=2, command=cmd,
                   bg=col, fg="black", activebackground="#F5F5F5",
                   highlightbackground=_BLUE, highlightthickness=1,
                   font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=1)

    # ══════════════════════════════════════════════════
    # ④ AI 分析结果 ScrolledText
    # ══════════════════════════════════════════════════
    result_frame = _tk.LabelFrame(root, text=" 💡 AI 研判结果 ",
                                   bg=_BG, fg=_GOLD,
                                   font=("TkDefaultFont", 10, "bold"))
    result_frame.pack(fill=_tk.BOTH, expand=True, padx=10, pady=(2, 10))

    text_widget = _st.ScrolledText(
        result_frame, wrap=_tk.WORD, bg=_PANEL, fg=_FG,
        font=("TkDefaultFont", font_size[0]),
        insertbackground=_FG, padx=12, pady=10,
        relief=_tk.FLAT, borderwidth=0,
    )
    text_widget.pack(fill=_tk.BOTH, expand=True, padx=6, pady=6)

    # 先放个欢迎引导
    text_widget.insert("end", """📈 资金路线推演 · AI 多风格研判

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

点上面 🤖 大V风格按钮（简放 / 陈小群 / 赵老哥 / 冯柳 / 段永平 / 国家队）
   ↓
AI 会用该大V的交易体系，结合当前板块数据进行专属分析
   ↓
「🔍 AI 多风格全分析」一键跑 7 种风格，对比不同视角的研判

点「🔄 刷新实时数据」更新板块排行 / 概念热点 / 宏观参考

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

数据来源：同花顺行业/概念板块 + Akshare 实时行情 + AI 代理 (localhost:8787)
""")

    # ── 字体切换 ──
    def _rebuild_text_widget():
        text_widget.config(font=("TkDefaultFont", font_size[0]))

    # ── 刷新数据（后台线程） ──
    def _refresh_data():
        status_lbl.config(text="⏳ 拉取实时板块数据...", fg=_GOLD)
        def _w():
            d = _get_mainline_route_data()
            _time.sleep(0.1)
            _after(lambda: _update_data_cards(d))
        _th.Thread(target=_w, daemon=True).start()

    def _update_data_cards(d):
        sectors = d.get("sectors", [])
        themes = d.get("hot_themes", [])
        card_top_ind.config(text=f"{sectors[0][0] if sectors else '-'}  {sectors[0][1]:+.2f}%" if sectors else "-")
        card_top_con.config(text=f"{themes[0][0] if themes else '-'}  {themes[0][1]:+.2f}%" if themes else "-")
        card_themes.config(text=f"{len(sectors)} 行业 · {len(themes)} 概念")
        card_date.config(text=d.get("date_str", ""))
        status_lbl.config(text=f"✅ 数据已更新 {d.get('date_str','')}", fg=_GREEN)

    # ── AI 单风格分析 ──
    def _trigger_ai():
        gid = active_guru.get()
        style = next((s for s in STYLES if s["id"] == gid), None)
        if not style:
            return
        _run_single_style_ai(style)

    # ── AI 全风格分析（串行） ──
    def _trigger_all_styles():
        text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
        text_widget.insert("end", "🤖 AI 多风格全分析 — 正在串行调用 7 种大V视角...\n\n")
        text_widget.config(state=_tk.DISABLED)
        status_lbl.config(text="⏳ 串行 AI 分析中（约 2-5 分钟）...", fg=_GOLD)

        def _w():
            results = []
            for s in STYLES:
                try:
                    r = _call_ai(s)
                    results.append((s, r))
                except Exception as e:
                    results.append((s, f"❌ 调用失败: {e}"))
            _after(lambda: _show_all_results(results))

        _th.Thread(target=_w, daemon=True).start()

    def _show_all_results(results):
        text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
        for s, r in results:
            text_widget.insert("end", f"\n{'═'*50}\n")
            text_widget.insert("end", f"  {s['icon']}  {s['name']}\n")
            text_widget.insert("end", f"{'═'*50}\n\n")
            text_widget.insert("end", r + "\n\n")
        text_widget.see("end")
        text_widget.config(state=_tk.DISABLED)
        status_lbl.config(text="✅ 全风格分析完成", fg=_GREEN)

    def _run_single_style_ai(style):
        text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
        text_widget.insert("end", f"⏳ [{style['icon']} {style['name']}] AI 分析中，请稍候...\n\n")
        text_widget.config(state=_tk.DISABLED)
        status_lbl.config(text=f"⏳ {style['name']} 正在分析...", fg=_GOLD)

        def _w():
            try:
                r = _call_ai(style)
                _after(lambda: _show_single_result(style, r))
            except Exception as e:
                import traceback; traceback.print_exc()
                _after(lambda: _show_single_result(style, f"❌ AI 调用异常: {e}"))

        _th.Thread(target=_w, daemon=True).start()

    def _show_single_result(style, result_text):
        text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
        text_widget.insert("end", f"{style['intro']}\n")
        text_widget.insert("end", f"{'═'*50}\n\n")
        text_widget.insert("end", result_text + "\n")
        text_widget.see("end")
        text_widget.config(state=_tk.DISABLED)
        status_lbl.config(text=f"✅ {style['name']} 分析完成", fg=_GREEN)

    # ── 真正的 AI 调用（后台线程中执行）── 直接走代理，跳过 60s 直连 caller 链
    def _call_ai(style):
        """直接走 localhost:8787 代理（签名+20s timeout），避免 _robust_ai_call 的 60s 直连"""
        d = _get_mainline_route_data()

        # 构造数据上下文
        sectors_lines = ""
        for i, (name, chg, amt, ld, ld_chg, ud, lim) in enumerate(d.get("sectors", [])[:10], 1):
            sectors_lines += f"  {i}. {name}  涨跌 {chg:+.2f}%  成交 {amt}亿  领涨 {ld}({ld_chg:+.2f}%)  {ud}\n"

        themes_lines = ""
        for i, (name, chg) in enumerate(d.get("hot_themes", [])[:6], 1):
            themes_lines += f"  {i}. {name}  {chg:+.2f}%\n"

        macro_lines = ""
        for k, v in d.get("macro", {}).items():
            macro_lines += f"  · {k}: {v}\n"

        now_str = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

        # 大V style 额外信息注入 prompt
        style_extra = ""
        if style["id"] == "ji Fang":
            style_extra = "\n【简放风格重点】请从以下维度展开：\n① 今日最强行业是否有产业级赛道逻辑？\n② 北向资金/基金/社保近期是否在该赛道建仓？\n③ 估值与行业平均对比是否有安全边际？\n④ 未来 3-6 个月业绩增长确定性如何？"
        elif style["id"] == "xiaoqun":
            style_extra = "\n【陈小群风格重点】请从情绪周期视角展开：\n① 当前处于情绪周期哪个阶段？（冰点/主升/高潮/退潮）\n② 今日最强行业是否是当前主线总龙头板块？\n③ 该板块是否出现连板≥5的龙头股？\n④ 建议仓位（10%/50%/≤20%/空仓）"
        elif style["id"] == "zhao_lao_ge":
            style_extra = "\n【赵老哥风格重点】请回答：\n① 今日哪些板块有连续3板以上的龙头？\n② 最强板块的领涨股量能是否配合（倍量/放量过前高）？\n③ 是否有≥3只同题材涨停的板块联动效应？\n④ 操作建议：只做龙头还是可以做跟风？"
        elif style["id"] == "feng_liu":
            style_extra = "\n【冯柳风格重点】请从逆向赔率视角展开：\n① 当前哪些板块/个股是市场错杀后逻辑未被破坏的？\n② 最近3个月下跌超过30%且基本面未恶化的有哪些？\n③ 行业一致悲观时是否有赔率覆盖胜率的机会？\n④ 是否要等第一个季报验证后再介入？"
        elif style["id"] == "duanyongping":
            style_extra = "\n【段永平风格重点】请从价值投资7维展开：\n① 今日最强行业里的龙头公司，商业模式如何？\n② 盈利质量与现金流是否优秀？\n③ 估值与历史分位对比处于什么位置？\n④ 是否值得10年以上长期持有？买入时机在哪里？"
        elif style["id"] == "guojia_dui":
            style_extra = "\n【国家队/主力视角重点】请分析：\n① 今日最强板块是否有北向/Lof/社保/QFII 资金持续流入？\n② 3万亿量化私募当前是加仓哪个方向？\n③ 板块是否处于筹码低位（20日线上、密集成交区上方）？\n④ 关键指数关口（如3000/3200）是否有护盘信号？"

        prompt = f"""请基于以下今日A股实时板块数据，从「{style['name']}」的视角进行深度研判。

📊 今日行业板块涨幅 TOP10:
{sectors_lines if sectors_lines else "（数据暂不可用）"}

🔥 今日热门概念 TOP8:
{themes_lines if themes_lines else "（数据暂不可用）"}

🌐 宏观参考:
{macro_lines if macro_lines else "（数据暂不可用）"}

🕐 分析时间: {now_str}
{style_extra}

请输出完整的研判报告，结构要求：
═══════════════════════════════════
{style['icon']} {style['name']} · 主线资金路线研判（{now_str}）
═══════════════════════════════════

一、{style['name']}风格核心判断
（2-3段话，说清当前市场状态的定性）

二、今日主线板块分析
（2-3个最值得关注的板块，配领涨股、筹码结构、资金态度）

三、接下来 1-2 周主线走势推演
（资金路线可能的演变方向，新老主线切换信号）

四、操作建议
（建议买入/观望/空仓，具体板块和个股方向）

五、风险提示
（用{style['name']}风格特有的风险点来写）

═══════════════════════════════════"""

        # ⚡ 直接走 localhost:8787 代理（签名 + 20s timeout），跳过 _robust_ai_call 的 60s 直连 caller 链
        try:
            import requests as _req
            import hmac as _hmac, hashlib as _hashlib, secrets as _secrets, os as _os

            _secret_path = "/tmp/stock_ai_proxy.secret"
            if not _os.path.exists(_secret_path):
                return "❌ AI 代理 secret 文件不存在"
            _proxy_secret = open(_secret_path).read().strip()
            _nonce = _secrets.token_hex(8)
            _proxy_token = _hmac.new(
                _proxy_secret.encode(),
                ("ai_proxy" + _nonce).encode(),
                _hashlib.sha256).hexdigest()[:16]

            messages = []
            if style["system"]:
                messages.append({"role": "system", "content": style["system"]})
            messages.append({"role": "user", "content": prompt})

            headers = {
                "Content-Type": "application/json",
                "X-Nonce": _nonce,
                "X-Proxy-Token": _proxy_token,
            }
            body = {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 2200,
                "temperature": 0.3,
            }

            resp = _req.post("http://127.0.0.1:8787/v1/chat/completions",
                             headers=headers, json=body, timeout=20)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if result and len(result.strip()) > 20:
                        return result
                    return "❌ AI 返回内容过短或为空"
                except Exception as _e:
                    return f"❌ AI 返回解析失败: {_e}"
            else:
                err_text = resp.text[:120]
                if "88a6" in err_text or "invalid" in err_text.lower() or "Authentication" in err_text:
                    return "🔑 DEEPSEEK_API_KEY 已过期！请更新 ~/.zshrc 中的 key 后重启代理和应用"
                return f"❌ AI 代理返回 {resp.status_code}: {err_text}"
        except Exception as e:
            return f"❌ AI 调用异常: {e}"

    # ── 线程安全的 after 调用 ──
    def _after(fn):
        try:
            tab.winfo_toplevel().after(0, fn)
        except Exception:
            fn()

    # 首次刷新一次数据
    tab.after(300, _refresh_data)

    return tab
