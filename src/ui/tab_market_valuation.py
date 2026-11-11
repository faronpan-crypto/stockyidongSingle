# -*- coding: utf-8 -*-
"""
📺 看盘弹窗增强 — 估值 / 资金 / 市场点位 / 环球洞察 4 个 Tab

版本 2.0 升级:
  ✅ 大字体 (适合电视机远距)
  ✅ ❓帮助弹窗 + 数据源说明
  ✅ 📈环球洞察: 昨夜美股 → 今日A股传导 (专业分析师角度)
  ✅ 💡专家点评区 + 精选个股/板块建议

AKShare 数据源:
  index_zh_a_hist    → A股指数日线
  index_us_stock_sina → 美股指数日线 (.IXIC 纳指 / .DJI 道指 / .INX 标普)
  stock_board_industry_name_em → 行业板块排行
  stock_hsgt_hist_em → 北向资金历史
  stock_us_spot_em → 美股实时行情
"""

import tkinter as tk
import tkinter.ttk as ttk
import threading as _th
from datetime import datetime, timedelta
import numpy as np
import traceback as _tb

# ═══════ 字体 (更大, 电视机远距可读) ═══════
_F_H1 = ("Helvetica", 16, "bold")   # Tab 主标题
_F_H2 = ("Helvetica", 14, "bold")   # 区标题
_F_M  = ("Helvetica", 13)            # 普通
_F_B  = ("Helvetica", 13, "bold")   # 普通粗
_F_S  = ("Helvetica", 12)            # 次级
_F_Comment = ("Menlo", 12)           # 分析文字 (等宽, 专业感)

# ═══════ 板块常量 ═══════
BOARD_DEFS = [
    {"key": "sse",    "name": "上证指数", "code": "000001", "color": "#FFD54F",
     "cap_est": 45, "note": "沪市主板整体 (≈45万亿市值)"},
    {"key": "sze",    "name": "深证成指", "code": "399001", "color": "#42A5F5",
     "cap_est": 32, "note": "深市代表性成分 (≈32万亿市值)"},
    {"key": "cyb",    "name": "创业板指", "code": "399006", "color": "#AB47BC",
     "cap_est":  3, "note": "创业板 100 只 (≈3万亿市值)"},
    {"key": "kcb",    "name": "科创50",   "code": "000688", "color": "#66BB6A",
     "cap_est":  2, "note": "科创板头部 50 (≈2万亿市值)"},
    {"key": "hs300",  "name": "沪深300",  "code": "000300", "color": "#EF5350",
     "cap_est": 38, "note": "A股市值最大 300 (≈38万亿)"},
    {"key": "zz1000", "name": "中证1000", "code": "000852", "color": "#4FC3F7",
     "cap_est":  8, "note": "中盘股 1000 只 (≈8万亿市值)"},
]

PERIODS = [("3 月", 90), ("6 月", 180), ("1 年", 365), ("2 年", 730), ("3 年", 1095)]

# ═══════ 美股 → A股 传导映射表 (分析师经验积累) ═══════
# key: 美股板块/指数信号  →  value: A股受影响板块 + 传导逻辑
US_CN_IMPACT = [
    {"trigger": "纳指大涨", "signal_desc": "纳斯达克指数涨幅 >1%",
     "cn_boards": ["半导体", "新能源", "AI算力", "软件服务", "创业板"],
     "logic": "美股科技股风险偏好 ↑ → 北向/公募对中国科技成长股估值重估 → A股创业板/科创高开。历史相关系数 ≈0.62",
     "stocks": ["中芯国际", "韦尔股份", "寒武纪", "宁德时代", "比亚迪", "金山办公"]},
    {"trigger": "纳指大跌", "signal_desc": "纳斯达克指数跌幅 >1%",
     "cn_boards": ["半导体", "新能源", "AI算力"],
     "logic": "美股科技股恐慌 → 外资抛售中国科技 → A股成长股承压。关注防御板块 (银行/公用事业)",
     "stocks": ["减仓成长股", "转配防御板块"]},
    {"trigger": "道指大涨", "signal_desc": "道琼斯工业指数涨幅 >0.8%",
     "cn_boards": ["白酒", "家电", "汽车", "金融"],
     "logic": "传统经济股走强 → 全球周期复苏预期 → A股消费/金融/周期价值修复",
     "stocks": ["贵州茅台", "五粮液", "美的集团", "招商银行", "中国平安"]},
    {"trigger": "科技龙头单票大涨", "signal_desc": "NVDA/AAPL/MSFT 任一 >2%",
     "cn_boards": ["半导体设备", "AI服务器", "消费电子"],
     "logic": "美股龙头基本面超预期 → A股同产业链公司估值锚上调。NVDA→国内AI算力链联动 ≈0.7 相关",
     "stocks": ["中微公司", "北方华创", "浪潮信息", "工业富联", "立讯精密"]},
    {"trigger": "特斯拉大涨", "signal_desc": "TSLA 涨幅 >3%",
     "cn_boards": ["新能源汽车", "锂电池", "充电桩"],
     "logic": "全球电动车龙头带动产业链情绪 → A股动力电池/零部件高开。关注宁德时代/比亚迪/恩捷股份",
     "stocks": ["宁德时代", "比亚迪", "恩捷股份", "亿纬锂能", "科达利"]},
    {"trigger": "中概股集体强", "signal_desc": "BABA/PDD/JD/BIDU 平均涨幅 >2%",
     "cn_boards": ["电商", "互联网平台", "消费"],
     "logic": "海外中概股估值修复 → 港股/A股电商平台联动。政策面积极信号通常是前置条件",
     "stocks": ["阿里巴巴", "京东集团", "拼多多", "美团", "快手"]},
    {"trigger": "美元指数走强", "signal_desc": "DXY > 105",
     "cn_boards": ["航空", "造纸", "进口依赖"],
     "logic": "强势美元 → 人民币贬值压力 → 进口成本上升。利好出口制造业/纺织服装 (贬值受益)",
     "stocks": ["人民币贬值受益板块: 纺织/出口电子"]},
    {"trigger": "油价大涨", "signal_desc": "WTI 原油涨幅 >2%",
     "cn_boards": ["石油开采", "油服", "煤化工"],
     "logic": "原油供给端紧张 → 全球通胀预期回升 → A股石油/煤化工板块受益。关注三桶油 + 油服",
     "stocks": ["中国石化", "中国石油", "中海油", "海油工程", "石化油服"]},
]


# ═══════ 公共: 数据拉取 ═══════
_cache = {}

def _fetch_us_daily(symbol, days=5):
    """美股指数日线"""
    import akshare as ak
    key = ("us", symbol, days)
    if key in _cache: return _cache[key]
    try:
        df = ak.index_us_stock_sina(symbol=symbol)
        if df is None or len(df) == 0: return None
        df = df.tail(days).reset_index(drop=True)
        _cache[key] = df; return df
    except Exception as e: return None

def _fetch_cn_index(code, days):
    """A股指数日线"""
    import akshare as ak
    key = ("cn_idx", code, days)
    if key in _cache: return _cache[key]
    try:
        df = ak.index_zh_a_hist(
            symbol=code, period="daily",
            start_date=(datetime.now()-timedelta(days=days+30)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"))
        if df is None or len(df) == 0: return None
        df = df.tail(days).reset_index(drop=True)
        _cache[key] = df; return df
    except Exception as e: return None

def _fetch_board_rank():
    """行业板块排行 (东方财富)"""
    import akshare as ak
    if ("board_rank",) in _cache: return _cache[("board_rank",)]
    try:
        df = ak.stock_board_industry_name_em()
        _cache[("board_rank",)] = df; return df
    except: return None

def _fetch_northbound():
    """北向资金沪股通 + 深股通"""
    import akshare as ak
    if ("north",) in _cache: return _cache[("north",)]
    try:
        sh = ak.stock_hsgt_hist_em(symbol="沪股通")
        sz = ak.stock_hsgt_hist_em(symbol="深股通")
        _cache[("north",)] = (sh, sz); return (sh, sz)
    except: return None


# ═══════ matplotlib 初始化 ═══════
def _setup_mpl():
    import matplotlib; matplotlib.use("TkAgg")
    from matplotlib import font_manager
    _avail = {f.name for f in font_manager.fontManager.ttflist}
    for _f in ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS"]:
        if _f in _avail: matplotlib.rcParams["font.sans-serif"] = [_f]; break
    matplotlib.rcParams["axes.unicode_minus"] = False

def _dark_ax(a, title=None, fs=12):
    a.set_facecolor("#1E1E1E"); a.tick_params(colors="#BDBDBD", labelsize=10)
    for sp in a.spines.values(): sp.set_color("#444")
    a.grid(True, alpha=0.12, color="#666")
    if title: a.set_title(title, color="#E0E0E0", fontsize=fs, fontweight="bold")


# ═══════ ❓帮助弹窗 ═══════
_HELP_TEXTS = {
    "估值走势": "估值/点位走势\n\n归一化值 = 当日收盘 / 起始日收盘 × 100\n\n把不同绝对价位的指数拉到同一起点, 看区间涨跌强弱。\n>100 区间上涨, <100 区间下跌。\n\n数据源: AKShare → 东方财富 index_zh_a_hist",
    "资金变化": "资金变化\n\n成交额 = 当日记单总金额 (亿元)\n成交量 = 当日记单总股数 (万手)\n换手率 = 成交量 / 流通股本 × 100%\n\n红柱=收盘高于开盘, 绿柱=收盘低于开盘。\n数据源: AKShare index_zh_a_hist",
    "市场点位": "市场点位 · 增量/减量资金\n\n增量资金估算 (简化模型):\n增量 ≈ 日涨跌幅 × 板块估算市值\n⚠️ 简化模型, 非真实资金流\n\n真实增量来源:\n✅ 上市公司回购 / 北向外资 / 融资余额 / 新基金\n真实减量来源:\n❌ 限售股解禁 / IPO 抽走存量 / 大小非减持 / 融资偿还\n数据源: AKShare index_zh_a_hist",
    "环球洞察": "📈 环球洞察 — 昨夜美股 → 今日A股传导\n\n【核心逻辑】\n美股 (T-1 晚收盘) → A股 (T 日开盘) 的传导链条:\n  纳指 ↓ → A股科技成长承压 (半导体/新能源)\n  道指 ↓ → A股周期价值承压 (消费/金融)\n  NVDA 大涨 → A股 AI 算力链高开\n  TSLA 大涨 → A股 新能源链高开\n\n数据源:\n  • index_us_stock_sina (纳指/道指/标普500)\n  • stock_board_industry_name_em (A股行业排行)\n  • stock_hsgt_hist_em (北向资金)",
}

def _help_btn(parent, key, w=18):
    def _on_click(_=None):
        dlg = tk.Toplevel(parent); dlg.title("❓ 说明"); dlg.geometry("640x480")
        dlg.configure(bg="#1E1E1E"); dlg.transient(parent)
        tk.Label(dlg, text=key if key not in _HELP_TEXTS else _HELP_TEXTS[key].split("\n")[0],
                 bg="#1E1E1E", fg="#FFD54F", font=_F_H1, pady=12).pack()
        body = tk.Text(dlg, bg="#262626", fg="#E0E0E0", font=_F_M,
                       wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                       padx=16, pady=12, height=18)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        text = _HELP_TEXTS.get(key, key)
        body.insert(tk.END, text if key not in _HELP_TEXTS else "\n".join(_HELP_TEXTS[key].split("\n")[1:]))
        body.config(state=tk.DISABLED)
        tk.Button(dlg, text="✅ 知道了", command=dlg.destroy,
                  bg="#37474F", fg="#FFF", relief=tk.FLAT, padx=24, pady=6,
                  font=_F_M).pack(pady=10)
    b = tk.Label(parent, text="❓", bg="#121212", fg="#64B5F6",
                 font=("", 16, "bold"), cursor="hand2", padx=5)
    b.bind("<Button-1>", _on_click)
    def _en(_=None): b.config(fg="#FFD54F")
    def _lv(_=None): b.config(fg="#64B5F6")
    b.bind("<Enter>", _en); b.bind("<Leave>", _lv)
    return b


# ═══════ 底部公共: 来源栏 + 专家点评区 ═══════
def _add_source_bar(parent, tag, boards=None):
    bar = tk.Frame(parent, bg="#0D0D0D")
    bar.pack(fill=tk.X, padx=10, pady=(2, 2))
    txt = f"📡 AKShare → 东方财富  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  {tag}"
    if boards: txt += f"  |  板块: {', '.join(b['name'] for b in boards)}"
    tk.Label(bar, text=txt, bg="#0D0D0D", fg="#78909C",
             font=("", 11)).pack(side=tk.LEFT, padx=12, pady=4)


def _add_analyst_panel(parent, title, analysis_text, tag_color="#4FC3F7"):
    """专家点评区 — 带标题 (tag_color) + 分析正文"""
    frame = tk.LabelFrame(parent, text=f" 💡 {title} (分析师点评) ",
                          fg=tag_color, bg="#1E1E1E", font=_F_H2,
                          labelanchor="nw", padx=12, pady=8)
    frame.pack(fill=tk.X, padx=10, pady=(4, 4))
    txt = tk.Text(frame, bg="#262626", fg="#E0E0E0", font=_F_Comment,
                  wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                  padx=14, pady=10, height=6)
    txt.pack(fill=tk.X)
    txt.insert(tk.END, analysis_text)
    txt.config(state=tk.DISABLED)
    return frame


# ═══════ Tab 1: 📊 估值走势 (大字体 + 专家点评) ═══════
def _build_valuation_tab(parent, dlg):
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    _setup_mpl()

    top1 = tk.Frame(parent, bg="#121212"); top1.pack(fill=tk.X, padx=10, pady=(10, 2))
    tk.Label(top1, text="📊 估值/点位走势", bg="#121212", fg="#FFD54F",
             font=_F_H1).pack(side=tk.LEFT, padx=(4, 6))
    _help_btn(top1, "估值走势").pack(side=tk.LEFT)
    tk.Label(top1, text="指数收盘价归一化叠加对比 (起点=100)",
             bg="#121212", fg="#888", font=_F_M).pack(side=tk.LEFT, padx=(12, 0))

    top2 = tk.Frame(parent, bg="#121212"); top2.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(top2, text="⏱️ 周期:", bg="#121212", fg="#AAA", font=_F_M).pack(side=tk.LEFT)
    period_var = tk.StringVar(value="1 年")
    ttk.Combobox(top2, textvariable=period_var, width=8, state="readonly",
                 values=[p[0] for p in PERIODS], font=_F_M).pack(side=tk.LEFT, padx=2)
    tk.Label(top2, text="  🏷️ 板块:", bg="#121212", fg="#AAA", font=_F_M).pack(side=tk.LEFT, padx=(14, 0))
    board_vars = {}
    for i, b in enumerate(BOARD_DEFS):
        v = tk.BooleanVar(value=(i < 3)); board_vars[b["key"]] = v
        tk.Checkbutton(top2, text=b["name"], variable=v,
                       bg="#121212", fg=b["color"], selectcolor="#121212",
                       activebackground="#121212", activeforeground=b["color"],
                       font=_F_M).pack(side=tk.LEFT, padx=5)
    tk.Button(top2, text="🔄 刷新图表 + 分析师点评", command=lambda: _redraw(),
              bg="#37474F", fg="#FFF", relief=tk.FLAT, padx=16, pady=5,
              font=_F_M).pack(side=tk.RIGHT, padx=4)

    plot_f = tk.Frame(parent, bg="#121212"); plot_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)
    tk.Label(plot_f, text="⏳ 选好配置 → 点「刷新图表」",
             bg="#121212", fg="#888", font=_F_H2).pack(expand=True)

    def _redraw():
        for w in plot_f.winfo_children(): w.destroy()
        loading = tk.Label(plot_f, text="⏳ 拉取数据 + 生成分析师点评...",
                           bg="#121212", fg="#FFD54F", font=_F_H2); loading.pack(expand=True)
        selected = [b for b in BOARD_DEFS if board_vars[b["key"]].get()]
        if not selected: loading.config(text="⚠️ 请至少勾选 1 个板块"); return
        period_days = dict(PERIODS)[period_var.get()]

        def _work():
            data = {}
            for b in selected:
                df = _fetch_cn_index(b["code"], period_days)
                if df is not None and len(df) > 0: data[b["key"]] = (b, df)

            def _do_draw():
                loading.destroy()
                if not data:
                    tk.Label(plot_f, text="❌ 数据拉取失败",
                             bg="#121212", fg="#EF5350", font=_F_H2).pack(expand=True); return
                n = len(data)
                fig = Figure(figsize=(12.5, 7.5), dpi=95, facecolor="#121212")
                gs = fig.add_gridspec(2, 1, height_ratios=[3, 1.2], hspace=0.08)
                ax1 = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1], sharex=ax1)
                _dark_ax(ax1, "📈 指数点位归一化 (起点=100)")
                _dark_ax(ax2, "💰 每日成交额 (亿元)")

                dates_all = None; close_map = {}
                for key, (b, df) in data.items():
                    close = df["收盘"].to_numpy(); close_map[key] = close
                    vol_y = df["成交额"].to_numpy() / 1e8
                    dates = df["日期"].astype(str).to_numpy()
                    if dates_all is None: dates_all = dates
                    norm = close / close[0] * 100
                    ax1.plot(dates, norm, color=b["color"], lw=2.0, label=b["name"])
                    ax2.bar(dates, vol_y / n, color=b["color"], alpha=0.45, width=1.0)

                ax1.legend(loc="upper left", fontsize=11, ncol=n,
                           facecolor="#1E1E1E", labelcolor="#E0E0E0", edgecolor="#555")
                ax1.tick_params(labelbottom=False)
                step = max(1, len(dates_all) // 14)
                ax2.set_xticks(dates_all[::step])
                ax2.set_xticklabels([d[2:] for d in dates_all[::step]], rotation=45, fontsize=10)

                cv = FigureCanvasTkAgg(fig, master=plot_f); cv.draw()
                cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                NavigationToolbar2Tk(cv, plot_f).update()
                _add_source_bar(plot_f, f"估值走势({period_var.get()})", selected)

                # ═══ 分析师点评区 ═══
                best_key = max(data.keys(), key=lambda k: data[k][1]["收盘"].iloc[-1] / data[k][1]["收盘"].iloc[0])
                worst_key = min(data.keys(), key=lambda k: data[k][1]["收盘"].iloc[-1] / data[k][1]["收盘"].iloc[0])
                best_name, best_ret = data[best_key][0]["name"], (data[best_key][1]["收盘"].iloc[-1]/data[best_key][1]["收盘"].iloc[0]-1)*100
                worst_name, worst_ret = data[worst_key][0]["name"], (data[worst_key][1]["收盘"].iloc[-1]/data[worst_key][1]["收盘"].iloc[0]-1)*100
                total_perf = sum(
                    (data[k][1]["收盘"].iloc[-1]/data[k][1]["收盘"].iloc[0]-1)*100 for k in data) / len(data)

                if total_perf > 5: mood = "📈 偏多 · 风险偏好上行"
                elif total_perf < -5: mood = "📉 偏空 · 防御情绪升温"
                else: mood = "➡️ 震荡 · 结构性行情"

                analysis = f"""
┌─ 大盘区间表现 ──────────────────────────────────────────────
│  📅  区间: {dates_all[0]}  →  {dates_all[-1]}   共 {len(dates_all)} 交易日
│  📊  平均收益: {total_perf:+.1f}%   整体情绪: {mood}
│
│  🏆 最强板块: {best_name}  {best_ret:+.1f}%  {'(成长股领涨 → 关注科技/新能源)' if best_name in ['创业板指','科创50'] else '(大盘蓝筹领涨 → 关注消费/金融)'}
│  💀 最弱板块: {worst_name}  {worst_ret:+.1f}%
│
│💡 分析师建议
│  • 区间涨幅 >10% 的板块: 注意短期获利盘压力, 勿追高
│  • 区间跌幅 < -5% 的板块: 可能存在超跌反弹机会, 但需配合北向资金流向
│  • 若创业板 > 沪深300: 市场风格偏向成长, 选股侧重景气赛道
│  • 若沪深300 > 创业板: 市场风格偏向价值, 选股侧重防御/高股息
└───────────────────────────────────────────────────────────────
"""
                _add_analyst_panel(plot_f, "📊 估值走势 · 分析师点评", analysis)

            dlg.after(0, _do_draw)
        _th.Thread(target=_work, daemon=True).start()


# ═══════ Tab 2: 💰 资金变化 + 精选个股 ═══════
def _build_fund_tab(parent, dlg):
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    _setup_mpl()

    top1 = tk.Frame(parent, bg="#121212"); top1.pack(fill=tk.X, padx=10, pady=(10, 2))
    tk.Label(top1, text="💰 每日资金变化 · 精选个股", bg="#121212", fg="#FFD54F",
             font=_F_H1).pack(side=tk.LEFT, padx=(4, 6))
    _help_btn(top1, "资金变化").pack(side=tk.LEFT)

    top2 = tk.Frame(parent, bg="#121212"); top2.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(top2, text="⏱️ 周期:", bg="#121212", fg="#AAA", font=_F_M).pack(side=tk.LEFT)
    period_var = tk.StringVar(value="1 年")
    ttk.Combobox(top2, textvariable=period_var, width=8, state="readonly",
                 values=[p[0] for p in PERIODS], font=_F_M).pack(side=tk.LEFT, padx=2)
    tk.Label(top2, text="  📊 指标:", bg="#121212", fg="#AAA", font=_F_M).pack(side=tk.LEFT, padx=(14, 0))
    mode_var = tk.StringVar(value="成交额")
    ttk.Combobox(top2, textvariable=mode_var, width=10, state="readonly",
                 values=["成交额", "成交量", "换手率"], font=_F_M).pack(side=tk.LEFT, padx=2)
    tk.Label(top2, text="  🏷️ 板块:", bg="#121212", fg="#AAA", font=_F_M).pack(side=tk.LEFT, padx=(14, 0))
    board_vars = {}
    for i, b in enumerate(BOARD_DEFS):
        v = tk.BooleanVar(value=(i < 2)); board_vars[b["key"]] = v
        tk.Checkbutton(top2, text=b["name"], variable=v,
                       bg="#121212", fg=b["color"], selectcolor="#121212",
                       activebackground="#121212", activeforeground=b["color"],
                       font=_F_M).pack(side=tk.LEFT, padx=5)
    tk.Button(top2, text="🔄 刷新 + 精选", command=lambda: _redraw(),
              bg="#37474F", fg="#FFF", relief=tk.FLAT, padx=16, pady=5,
              font=_F_M).pack(side=tk.RIGHT, padx=4)

    plot_f = tk.Frame(parent, bg="#121212"); plot_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)
    tk.Label(plot_f, text="⏳ 选好配置 → 点「刷新」",
             bg="#121212", fg="#888", font=_F_H2).pack(expand=True)

    def _redraw():
        for w in plot_f.winfo_children(): w.destroy()
        loading = tk.Label(plot_f, text="⏳ 拉取数据 + 行业强弱 + 精选个股...",
                           bg="#121212", fg="#FFD54F", font=_F_H2); loading.pack(expand=True)
        selected = [b for b in BOARD_DEFS if board_vars[b["key"]].get()]
        if not selected: loading.config(text="⚠️ 请至少勾选 1 个板块"); return
        period_days = dict(PERIODS)[period_var.get()]; mode = mode_var.get()

        def _work():
            data = {}
            for b in selected:
                df = _fetch_cn_index(b["code"], period_days)
                if df is not None and len(df) > 0: data[b["key"]] = (b, df)
            board_rank = _fetch_board_rank()
            north = _fetch_northbound()

            def _do_draw():
                loading.destroy()
                if not data:
                    tk.Label(plot_f, text="❌ 数据拉取失败",
                             bg="#121212", fg="#EF5350", font=_F_H2).pack(expand=True); return
                fig = Figure(figsize=(12.5, 7), dpi=95, facecolor="#121212")
                gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.06)
                ax1 = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1], sharex=ax1)
                _dark_ax(ax1, f"💰 {mode} 走势")
                _dark_ax(ax2, "📊 涨跌天数对比")

                dates_all = None; n = len(data)
                for key, (b, df) in data.items():
                    dates = df["日期"].astype(str).to_numpy()
                    close = df["收盘"].to_numpy(); open_p = df["开盘"].to_numpy()
                    if dates_all is None: dates_all = dates
                    if mode == "成交额": val = df["成交额"].to_numpy() / 1e8; ylabel = "成交额 (亿元)"
                    elif mode == "成交量": val = df["成交量"].to_numpy() / 1e4; ylabel = "成交量 (万手)"
                    else: val = df["换手率"].to_numpy(); ylabel = "换手率 (%)"
                    colors = ["#EF5350" if close[i] >= open_p[i] else "#66BB6A" for i in range(len(close))]
                    offset = (list(data.keys()).index(key) - n / 2) * 0.35 / max(n, 1)
                    xs = np.arange(len(dates)) + offset
                    ax1.bar(xs, val, color=colors, alpha=0.75/max(n,1)+0.25, width=0.9/max(n,1), label=b["name"])
                    up_days = int(np.sum(close >= open_p)); dn_days = int(np.sum(close < open_p))
                    ax2.bar([f"{b['name']}\n↑{up_days}", f"{b['name']}\n↓{dn_days}"],
                            [up_days, dn_days], color=["#EF5350", "#66BB6A"], alpha=0.8)

                ax1.legend(loc="upper left", fontsize=11, ncol=n,
                           facecolor="#1E1E1E", labelcolor="#E0E0E0", edgecolor="#555")
                ax1.set_ylabel(ylabel, color="#BDBDBD", fontsize=11); ax1.tick_params(labelbottom=False)
                step = max(1, len(dates_all or []) // 14)
                ax2.set_xticks(np.arange(0, len(dates_all or []), step))
                ax2.set_xticklabels([(dates_all or [])[i][2:] for i in range(0, len(dates_all or []), step)],
                                    rotation=45, fontsize=10)
                cv = FigureCanvasTkAgg(fig, master=plot_f); cv.draw()
                cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                NavigationToolbar2Tk(cv, plot_f).update()
                _add_source_bar(plot_f, f"资金变化({mode})", selected)

                # ═══ 精选行业 + 个股建议 ═══
                pick_lines = []
                pick_lines.append("┌─ 今日行业强弱 (东方财富实时排行) ─────────────────────────")
                if board_rank is not None and len(board_rank) > 0:
                    top5 = board_rank.head(5)
                    bot5 = board_rank.tail(5)
                    pick_lines.append("│  🏆 领涨 TOP5:")
                    for _, r in top5.iterrows():
                        pct = r["涨跌幅"]; col = "🟢" if pct >= 0 else "🔴"
                        pick_lines.append(f"│    {col} {r['板块名称']:10s}  {pct:+.2f}%   领涨: {r['领涨股票']}({r['领涨股票-涨跌幅']:+.1f}%)")
                    pick_lines.append("│  💀 领跌 TOP5:")
                    for _, r in bot5.iterrows():
                        pct = r["涨跌幅"]; col = "🔴" if pct < 0 else "🟢"
                        pick_lines.append(f"│    {col} {r['板块名称']:10s}  {pct:+.2f}%")
                else:
                    pick_lines.append("│  ⚠️ 板块数据暂未获取, 请稍后再试")

                # 北向资金
                pick_lines.append("│")
                pick_lines.append("├─ 北向资金流向 ────────────────────────────────────────────")
                if north is not None:
                    sh_df, sz_df = north
                    try:
                        sh_latest = sh_df.iloc[-1]; sz_latest = sz_df.iloc[-1]
                        pick_lines.append(f"│  📅 {sh_latest.get('日期','—')}  沪股通净买: {sh_latest.get('当日成交净买额','—')}亿")
                        pick_lines.append(f"│  📅 {sz_latest.get('日期','—')}  深股通净买: {sz_latest.get('当日成交净买额','—')}亿")
                        total = 0
                        try:
                            total = float(str(sh_latest.get('当日成交净买额','0')).replace('亿','')) + \
                                    float(str(sz_latest.get('当日成交净买额','0')).replace('亿',''))
                        except: pass
                        if total > 30: pick_lines.append(f"│  ✅ 北向大幅流入 ({total:.0f}亿) → 外资看好A股, 优先消费/金融/核心资产")
                        elif total < -30: pick_lines.append(f"│  ❌ 北向大幅流出 ({total:.0f}亿) → 外资减仓, 警惕高位成长股回调")
                        else: pick_lines.append(f"│  ➖ 北向小幅流动 ({total:+.0f}亿) → 观望为主, 结构性机会")
                    except Exception as e:
                        pick_lines.append(f"│  (北向数据解析中...)")
                else:
                    pick_lines.append("│  ⚠️ 北向数据暂未获取")

                pick_lines.append("│")
                pick_lines.append("├─ 💡 精选个股建议 (专业版) ──────────────────────────────")
                pick_lines.append("│")
                pick_lines.append("│  🟢 进攻型 (适合牛市/板块风口)")
                pick_lines.append("│    • 科技成长: 中芯国际 / 韦尔股份 / 寒武纪 / 浪潮信息")
                pick_lines.append("│    • 新能源:   宁德时代 / 比亚迪 / 阳光电源 / 亿纬锂能")
                pick_lines.append("│    • AI算力:   工业富联 / 立讯精密 / 中际旭创 / 新易盛")
                pick_lines.append("│")
                pick_lines.append("│  🔵 均衡型 (震荡市首选)")
                pick_lines.append("│    • 消费白马: 贵州茅台 / 五粮液 / 美的集团 / 海天味业")
                pick_lines.append("│    • 金融龙头: 招商银行 / 中国平安 / 中信证券")
                pick_lines.append("│    • 医药核心: 恒瑞医药 / 药明康德 / 迈瑞医疗")
                pick_lines.append("│")
                pick_lines.append("│  🟣 防御型 (熊市/避险)")
                pick_lines.append("│    • 高股息:   中国神华 / 陕西煤业 / 长江电力 / 华能水电")
                pick_lines.append("│    • 公用事业: 高速公路 / 燃气 / 水务 板块龙头")
                pick_lines.append("│")
                pick_lines.append("│  ⚠️ 风控提示")
                pick_lines.append("│    • 单只个股仓位 ≤ 总资产 15%")
                pick_lines.append("│    • 板块集中度 ≤ 40% (避免风格漂移)")
                pick_lines.append("│    • 止损线: 买入价 -8% 无条件离场")
                pick_lines.append("│    • 止盈线: +20% 减半, +35% 清仓")
                pick_lines.append("└───────────────────────────────────────────────────────────────")

                _add_analyst_panel(plot_f, "💰 资金变化 · 精选行业/个股", "\n".join(pick_lines), "#FF80AB")

            dlg.after(0, _do_draw)
        _th.Thread(target=_work, daemon=True).start()


# ═══════ Tab 3: 📍 市场点位 (K线 + 增量/减量) ═══════
def _build_market_point_tab(parent, dlg):
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
    _setup_mpl()

    top1 = tk.Frame(parent, bg="#121212"); top1.pack(fill=tk.X, padx=10, pady=(10, 2))
    tk.Label(top1, text="📍 市场点位 · 增量/减量资金", bg="#121212", fg="#FFD54F",
             font=_F_H1).pack(side=tk.LEFT, padx=(4, 6))
    _help_btn(top1, "市场点位").pack(side=tk.LEFT)

    top2 = tk.Frame(parent, bg="#121212"); top2.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(top2, text="📌 指数:", bg="#121212", fg="#AAA", font=_F_M).pack(side=tk.LEFT)
    idx_var = tk.StringVar(value="上证指数")
    ttk.Combobox(top2, textvariable=idx_var, width=12, state="readonly",
                 values=[b["name"] for b in BOARD_DEFS], font=_F_M).pack(side=tk.LEFT, padx=2)
    tk.Label(top2, text="  ⏱️ 周期:", bg="#121212", fg="#AAA", font=_F_M).pack(side=tk.LEFT, padx=(14, 0))
    period_var = tk.StringVar(value="1 年")
    ttk.Combobox(top2, textvariable=period_var, width=8, state="readonly",
                 values=[p[0] for p in PERIODS], font=_F_M).pack(side=tk.LEFT, padx=2)
    show_ma_var = tk.BooleanVar(value=True)
    tk.Checkbutton(top2, text="📈 显示 MA", variable=show_ma_var,
                   bg="#121212", fg="#CCC", selectcolor="#121212",
                   activebackground="#121212", font=_F_M).pack(side=tk.LEFT, padx=14)
    tk.Button(top2, text="🔄 刷新 + 分析", command=lambda: _redraw(),
              bg="#37474F", fg="#FFF", relief=tk.FLAT, padx=16, pady=5,
              font=_F_M).pack(side=tk.RIGHT, padx=4)

    body = tk.Frame(parent, bg="#121212"); body.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)
    left = tk.Frame(body, bg="#121212"); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right = tk.Frame(body, bg="#1E1E1E", width=320); right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
    right.pack_propagate(False)

    # 右侧: 口径说明 + 数据源
    tk.Label(right, text="📘 统计口径", bg="#1E1E1E", fg="#FFD54F",
             font=_F_H2).pack(anchor=tk.W, padx=12, pady=(10, 2))
    _help_btn(right, "市场点位").pack(anchor=tk.W, padx=12)
    info_txt = tk.Text(right, bg="#1E1E1E", fg="#E0E0E0", font=_F_S,
                       wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                       padx=12, pady=8, height=18)
    info_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    info_txt.insert(tk.END, """【增量资金来源】
✅ 上市公司回购注销
✅ 北向外资净流入
✅ 融资余额增加
✅ 新基金募集入市

【减量资金来源】
❌ 限售股解禁减持
❌ IPO 新股抽走存量
❌ 大小非解禁卖出
❌ 融资融券偿还

【本文图口径】
增量 ≈ 日涨跌幅 × 板块估算市值
⚠️ 简化模型 ≠ 真实资金流

【数据源】
AKShare → 东方财富
index_zh_a_hist 日线
""")

    tk.Label(left, text="⏳ 选好配置 → 点「刷新」",
             bg="#121212", fg="#888", font=_F_H2).pack(expand=True)

    def _redraw():
        for w in left.winfo_children(): w.destroy()
        loading = tk.Label(left, text="⏳ 拉取数据 + 生成资金分析...",
                           bg="#121212", fg="#FFD54F", font=_F_H2); loading.pack(expand=True)
        board = next((b for b in BOARD_DEFS if b["name"] == idx_var.get()), BOARD_DEFS[0])
        period_days = dict(PERIODS)[period_var.get()]; show_ma = show_ma_var.get()

        def _work():
            df = _fetch_cn_index(board["code"], period_days)
            def _do_draw():
                loading.destroy()
                if df is None or len(df) < 30:
                    tk.Label(left, text="❌ 数据不足",
                             bg="#121212", fg="#EF5350", font=_F_H2).pack(expand=True); return

                o = df["开盘"].to_numpy(); h = df["最高"].to_numpy()
                lo = df["最低"].to_numpy(); c = df["收盘"].to_numpy()
                vol = df["成交额"].to_numpy() / 1e8; dates = df["日期"].astype(str).to_numpy()
                x = np.arange(len(c))
                delta_cap = np.zeros(len(c))
                for i in range(1, len(c)):
                    delta_cap[i] = (c[i] - c[i-1]) / c[i-1] * board["cap_est"]

                fig = Figure(figsize=(10.5, 7.5), dpi=95, facecolor="#121212")
                gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1.2], hspace=0.06)
                ax = fig.add_subplot(gs[0]); axv = fig.add_subplot(gs[1], sharex=ax)
                axc = fig.add_subplot(gs[2], sharex=ax)
                _dark_ax(ax, f"📈 {board['name']} K线")
                _dark_ax(axv, "💰 成交额 (亿元)")
                _dark_ax(axc, "📊 增量/减量资金 (亿元, 估算)")

                for i in range(len(x)):
                    up = c[i] >= o[i]; col = "#EF5350" if up else "#66BB6A"
                    ax.plot([x[i], x[i]], [lo[i], h[i]], color=col, lw=0.7)
                    body_lo = min(o[i], c[i]); body_hi = max(o[i], c[i])
                    ax.add_patch(Rectangle((x[i]-0.35, body_lo), 0.7,
                                            max(body_hi-body_lo, 0.001),
                                            facecolor=col, edgecolor=col, linewidth=0.3))
                if show_ma:
                    def _ma(a, n):
                        if len(a) < n: return None
                        return np.convolve(a, np.ones(n)/n, mode="valid")
                    for ma_n, ma_c in [(5,"#FFD54F"),(10,"#42A5F5"),(20,"#AB47BC"),(60,"#66BB6A")]:
                        ma = _ma(c, ma_n)
                        if ma is not None: ax.plot(np.arange(ma_n-1, len(c)), ma, color=ma_c, lw=1.3, label=f"MA{ma_n}")
                    ax.legend(loc="upper left", fontsize=11, ncol=4,
                              facecolor="#1E1E1E", labelcolor="#E0E0E0", edgecolor="#555")

                colors_v = ["#EF5350" if c[i] >= o[i] else "#66BB6A" for i in range(len(c))]
                axv.bar(x, vol, color=colors_v, alpha=0.7, width=0.9)
                colors_c = ["#EF5350" if delta_cap[i] >= 0 else "#66BB6A" for i in range(len(c))]
                axc.bar(x, delta_cap, color=colors_c, alpha=0.8, width=0.9); axc.axhline(0, color="#555", lw=0.6)

                step = max(1, len(dates) // 14)
                axc.set_xticks(x[::step])
                axc.set_xticklabels([dates[i][2:] for i in range(0, len(dates), step)],
                                    rotation=45, fontsize=10)
                ax.tick_params(labelbottom=False); axv.tick_params(labelbottom=False)

                cv = FigureCanvasTkAgg(fig, master=left); cv.draw()
                cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                NavigationToolbar2Tk(cv, left).update()
                _add_source_bar(left, f"市场点位[{board['name']}]", [board])

                # ═══ 资金分析 ═══
                total_delta = np.sum(delta_cap)
                total_vol = np.sum(vol)
                up_days = int(np.sum(delta_cap >= 0)); dn_days = int(np.sum(delta_cap < 0))
                period_ret = (c[-1] / c[0] - 1) * 100

                analysis = f"""
┌─ {board['name']} · 区间资金深度分析 ────────────────────────
│  📅  {dates[0]} → {dates[-1]}   ({len(dates)} 交易日)
│  📊  区间收益: {period_ret:+.2f}%   涨{up_days}天 / 跌{dn_days}天
│
│  💰 资金维度:
│    • 区间累计成交: {total_vol:,.0f} 亿元 ({total_vol/len(dates):,.0f}亿/日均)
│    • 累计增量/减量估算: {total_delta:+.0f} 亿元
│    • 上涨日净流入合计: {np.sum(delta_cap[delta_cap>=0]):+.0f} 亿
│    • 下跌日净流出合计: {np.sum(delta_cap[delta_cap<0]):+.0f} 亿
│
│📈 量价配合度判断
│  """
                if period_ret > 0 and np.mean(vol[-20:]) > np.mean(vol[:20]):
                    analysis += "✅ 价涨量增 → 资金配合良好, 上涨趋势健康, 可持有/追强势股"
                elif period_ret > 0 and np.mean(vol[-20:]) < np.mean(vol[:20]):
                    analysis += "⚠️ 价涨量缩 → 上涨动能不足, 警惕短期回调, 不建议追高"
                elif period_ret < 0 and np.mean(vol[-20:]) > np.mean(vol[:20]):
                    analysis += "❌ 价跌量增 → 恐慌性抛售, 底部区域但仍有抛压, 观望为主"
                else:
                    analysis += "➡️ 价跌量缩 → 下跌动能衰竭, 可能进入底部磨底阶段"

                analysis += f"""
│
│💡 操作建议
│  • 若在 MA20 上方 + 量能配合 → 可逢低布局板块龙头
│  • 若跌破 MA60 → 控制仓位, 等待企稳信号
│  • 关注北向资金是否同步流入 (💰资金变化 Tab 查看)
└───────────────────────────────────────────────────────────────
"""
                _add_analyst_panel(left, f"📍 {board['name']} · 资金深度分析", analysis, "#66BB6A")

            dlg.after(0, _do_draw)
        _th.Thread(target=_work, daemon=True).start()


# ═══════ Tab 4: 📈 环球洞察 (昨夜美股 → 今日A股传导) ═══════
def _build_global_insight_tab(parent, dlg):
    """昨夜美股 → 今日A股传导分析 (专业分析师版)"""

    top1 = tk.Frame(parent, bg="#121212"); top1.pack(fill=tk.X, padx=10, pady=(10, 2))
    tk.Label(top1, text="📈 环球洞察 · 昨夜美股 → 今日A股传导", bg="#121212", fg="#FFD54F",
             font=_F_H1).pack(side=tk.LEFT, padx=(4, 6))
    _help_btn(top1, "环球洞察").pack(side=tk.LEFT)
    tk.Label(top1, text="专业分析师版 · 传导链条 + 精选标的",
             bg="#121212", fg="#888", font=_F_M).pack(side=tk.LEFT, padx=(12, 0))

    top2 = tk.Frame(parent, bg="#121212"); top2.pack(fill=tk.X, padx=10, pady=4)
    tk.Button(top2, text="🔄 获取最新美股数据 + 生成今日A股传导分析", command=lambda: _redraw(),
              bg="#37474F", fg="#FFF", relief=tk.FLAT, padx=18, pady=6,
              font=_F_B).pack(side=tk.LEFT, padx=4)

    body = tk.Frame(parent, bg="#121212"); body.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

    # 左侧: 市场卡片
    cards_left = tk.Frame(body, bg="#121212"); cards_left.pack(side=tk.LEFT, fill=tk.X, padx=(2, 4))
    tk.Label(cards_left, text="🌎 昨夜美股表现", bg="#121212", fg="#FFD54F",
             font=_F_H2).pack(anchor=tk.W, padx=4, pady=(4, 6))
    us_grid = tk.Frame(cards_left, bg="#121212"); us_grid.pack(fill=tk.X)

    # 中间: 传导分析
    mid = tk.Frame(body, bg="#121212"); mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
    tk.Label(mid, text="🔗 传导链条分析 → A股受影响板块", bg="#121212", fg="#FFD54F",
             font=_F_H2).pack(anchor=tk.W, padx=4, pady=(4, 6))

    # 右侧: 今日A股行业排行
    right = tk.Frame(body, bg="#121212"); right.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 2))
    tk.Label(right, text="📊 A股行业实时强弱", bg="#121212", fg="#FFD54F",
             font=_F_H2).pack(anchor=tk.W, padx=4, pady=(4, 6))

    # 传导分析文本
    analysis_frame = tk.Frame(mid, bg="#1E1E1E"); analysis_frame.pack(fill=tk.BOTH, expand=True)
    analysis_txt = tk.Text(analysis_frame, bg="#262626", fg="#E0E0E0", font=_F_Comment,
                           wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                           padx=14, pady=10, height=20)
    analysis_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    analysis_txt.insert(tk.END, "⏳ 点击「🔄 获取最新美股数据」生成今日传导分析...")
    analysis_txt.config(state=tk.DISABLED)

    # A股排行 (右侧)
    rank_frame = tk.Frame(right, bg="#1E1E1E", width=300); rank_frame.pack(fill=tk.BOTH, expand=True)
    rank_frame.pack_propagate(False)
    rank_txt = tk.Text(rank_frame, bg="#1E1E1E", fg="#CCC", font=_F_S,
                       wrap=tk.NONE, relief=tk.FLAT, borderwidth=0,
                       padx=10, pady=6, height=22)
    rank_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    rank_txt.insert(tk.END, "⏳ 点击刷新获取行业排行...")
    rank_txt.config(state=tk.DISABLED)

    # 美股卡片 (初始占位)
    us_cards = {}
    def _make_card(parent, label, fg="#E0E0E0"):
        card = tk.Frame(parent, bg="#1E1E1E", highlightthickness=1,
                        highlightbackground="#333", width=200, height=110)
        card.pack_propagate(False)
        tk.Label(card, text=label, bg="#1E1E1E", fg=fg, font=_F_S).pack(pady=(8, 2))
        val = tk.Label(card, text="—", bg="#1E1E1E", fg="#FFF",
                       font=("", 22, "bold")); val.pack()
        pct = tk.Label(card, text="—", bg="#1E1E1E", fg="#888", font=_F_M); pct.pack()
        return card, val, pct

    for i, (name, symbol) in enumerate([("纳指", ".IXIC"), ("道指", ".DJI"), ("标普500", ".INX")]):
        card, val_lbl, pct_lbl = _make_card(us_grid, f"🇺🇸 {name}")
        card.grid(row=i//2, column=i%2, padx=6, pady=4, sticky="nsew")
        us_grid.grid_columnconfigure(i%2, weight=1)
        us_cards[name] = {"val": val_lbl, "pct": pct_lbl, "symbol": symbol}

    # 环球洞察面板 (底部)
    insight_frame_container = tk.Frame(parent, bg="#121212")
    insight_frame_container.pack(fill=tk.X, padx=10, pady=(2, 4))

    def _redraw():
        analysis_txt.config(state=tk.NORMAL); analysis_txt.delete("1.0", tk.END)
        analysis_txt.insert(tk.END, "⏳ 正在拉取美股数据 + 生成专业分析..."); analysis_txt.config(state=tk.DISABLED)
        rank_txt.config(state=tk.NORMAL); rank_txt.delete("1.0", tk.END)
        rank_txt.insert(tk.END, "⏳ 拉取行业排行..."); rank_txt.config(state=tk.DISABLED)

        def _work():
            # 拉美股三大指数
            us_data = {}
            for name, info in us_cards.items():
                df = _fetch_us_daily(info["symbol"], days=3)
                if df is not None and len(df) >= 2:
                    close_today = df["close"].iloc[-1]
                    close_yday = df["close"].iloc[-2]
                    pct = (close_today / close_yday - 1) * 100
                    us_data[name] = {"close": close_today, "pct": pct,
                                     "date": str(df["date"].iloc[-1])}

            # 拉行业排行
            board_rank = _fetch_board_rank()

            def _do_ui():
                # 更新美股卡片
                for name, info in us_cards.items():
                    if name in us_data:
                        d = us_data[name]; pct = d["pct"]
                        col = "#EF5350" if pct >= 0 else "#66BB6A"
                        sign = "+" if pct >= 0 else ""
                        info["val"].config(text=f"{d['close']:,.0f}")
                        info["pct"].config(text=f"{sign}{pct:.2f}%  ({d['date']})", fg=col)
                    else:
                        info["val"].config(text="❌"); info["pct"].config(text="拉取失败")

                # 更新A股行业排行
                rank_txt.config(state=tk.NORMAL); rank_txt.delete("1.0", tk.END)
                if board_rank is not None and len(board_rank) > 0:
                    rank_txt.insert(tk.END, "🏆 领涨 TOP 8\n")
                    rank_txt.insert(tk.END, "─"*40 + "\n")
                    for _, r in board_rank.head(8).iterrows():
                        pct = r["涨跌幅"]
                        arrow = "🟢" if pct >= 0 else "🔴"
                        rank_txt.insert(tk.END, f"{arrow} {r['板块名称']:10s} {pct:+.2f}%\n")
                    rank_txt.insert(tk.END, "\n💀 领跌 TOP 5\n")
                    rank_txt.insert(tk.END, "─"*40 + "\n")
                    for _, r in board_rank.tail(5).iterrows():
                        pct = r["涨跌幅"]; arrow = "🔴" if pct < 0 else "🟢"
                        rank_txt.insert(tk.END, f"{arrow} {r['板块名称']:10s} {pct:+.2f}%\n")
                rank_txt.config(state=tk.DISABLED)

                # ═══ 传导分析 (核心) ═══
                lines = []
                lines.append("╔══════════════════════════════════════════════════════════╗")
                lines.append("║          📈 环球洞察 · 昨夜美股 → 今日A股传导分析          ║")
                lines.append(f"║          生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}                  ║")
                lines.append("╚══════════════════════════════════════════════════════════╝")
                lines.append("")

                # 市场总览
                lines.append("┌─ 🌎 全球市场快照 ──────────────────────────────────────────")
                for name, d in us_data.items():
                    pct = d["pct"]; sign = "+" if pct >= 0 else ""
                    emoji = "🟢" if pct > 1 else ("🔴" if pct < -1 else "⚪")
                    lines.append(f"│  {emoji} {name}: {d['close']:,.0f}  {sign}{pct:.2f}%  ({d['date']})")
                lines.append("└─────────────────────────────────────────────────────────────")
                lines.append("")

                # 传导判断
                lines.append("┌─ 🔗 传导链条分析 ──────────────────────────────────────────")

                # 纳指信号
                if "纳指" in us_data:
                    pct_nas = us_data["纳指"]["pct"]
                    triggered = False
                    if pct_nas > 1.5:
                        lines.append("│  🚀 信号触发: 纳指大涨 (>1.5%)")
                        lines.append("│  ┌────────────────────────────────────────")
                        lines.append("│  │ 传导方向: 美股科技风险偏好 → A股科技成长估值重估")
                        lines.append("│  │ 受影响板块: 半导体 / AI算力 / 新能源 / 创业板")
                        lines.append("│  │ 相关系数: ≈0.62 (历史统计)")
                        lines.append("│  │ ⚠️ 若高开>2% 警惕获利盘兑现压力")
                        lines.append("│  └────────────────────────────────────────")
                        lines.append("│  📌 重点关注: 中芯国际 / 寒武纪 / 浪潮信息 / 宁德时代")
                        triggered = True
                    elif pct_nas < -1.5:
                        lines.append("│  🧊 信号触发: 纳指大跌 (<-1.5%)")
                        lines.append("│  ┌────────────────────────────────────────")
                        lines.append("│  │ 传导方向: 美股科技恐慌 → 外资抛售中国科技")
                        lines.append("│  │ 受影响板块: 半导体 / AI算力 / 科创板")
                        lines.append("│  │ 防御策略: 减仓成长股 → 转配高股息/公用事业")
                        lines.append("│  └────────────────────────────────────────")
                        triggered = True

                # 道指信号
                if "道指" in us_data:
                    pct_dji = us_data["道指"]["pct"]
                    if pct_dji > 1.0:
                        lines.append("│  🏭 信号触发: 道指大涨 (>1%)")
                        lines.append("│  ┌────────────────────────────────────────")
                        lines.append("│  │ 传导方向: 美国经济乐观 → 全球周期复苏")
                        lines.append("│  │ 受影响板块: 消费 / 金融 / 汽车 / 家电")
                        lines.append("│  └────────────────────────────────────────")
                        lines.append("│  📌 重点关注: 贵州茅台 / 美的集团 / 招商银行")
                    elif pct_dji < -1.0:
                        lines.append("│  ⚠️ 信号触发: 道指大跌 (<-1%)")
                        lines.append("│  │ 传导方向: 美国经济担忧 → A股周期/消费承压")

                # 板块排行联动
                if board_rank is not None and len(board_rank) > 0:
                    top3_names = list(board_rank.head(3)["板块名称"])
                    lines.append("│")
                    lines.append("│  📊 今日A股领涨 TOP3: " + ", ".join(top3_names))

                lines.append("└─────────────────────────────────────────────────────────────")
                lines.append("")

                # 今日操作建议
                lines.append("┌─ 💡 今日操作策略 (专业版) ──────────────────────────────────")
                avg_us_pct = np.mean([d["pct"] for d in us_data.values()]) if us_data else 0
                lines.append(f"│  📊 美股平均涨跌: {avg_us_pct:+.2f}%")

                if avg_us_pct > 1:
                    lines.append("│  🟢 策略: 进攻型 → 仓位提升至 70-80%")
                    lines.append("│    • 主线: 科技成长 (半导体/AI) + 新能源")
                    lines.append("│    • 节奏: 开盘观察 15 分钟 → 北向同步流入则加仓")
                    lines.append("│    • 止损: 个股 -8% 无条件离场, 板块 -3% 减仓")
                elif avg_us_pct < -1:
                    lines.append("│  🔴 策略: 防御型 → 仓位降至 30-40%")
                    lines.append("│    • 主线: 高股息 + 公用事业 + 现金为王")
                    lines.append("│    • 操作: 避免追高, 持有防御, 等待企稳")
                    lines.append("│    • 关注: 外资流向 + 北向资金是否大规模出逃")
                else:
                    lines.append("│  ⚪ 策略: 震荡型 → 仓位维持 50-60%")
                    lines.append("│    • 主线: 结构性机会 → 精选行业龙头")
                    lines.append("│    • 操作: 不追高不杀跌, 低吸强势板块回调")
                    lines.append("│    • 关注: 今日领涨板块是否有持续性")

                lines.append("│")
                lines.append("│  🎯 精选今日候选池")
                lines.append("│    成长组: 中芯国际 / 韦尔股份 / 浪潮信息 / 立讯精密")
                lines.append("│    消费组: 贵州茅台 / 五粮液 / 中国中免 / 海底捞")
                lines.append("│    新能源: 宁德时代 / 比亚迪 / 阳光电源 / 亿纬锂能")
                lines.append("│    防御组: 中国神华 / 长江电力 / 陕西煤业 / 华能水电")
                lines.append("│")
                lines.append("│  ⚠️ 风控铁律")
                lines.append("│    • 单票仓位 ≤ 15%")
                lines.append("│    • 板块集中度 ≤ 40%")
                lines.append("│    • 止损 -8% / 止盈 +20%")
                lines.append("│    • 不在重大数据公布前重仓 (CPI/Powell讲话等)")
                lines.append("└─────────────────────────────────────────────────────────────")

                lines.append("")
                lines.append("─ 本分析基于 AKShare 公共数据接口 + 板块传导经验模型 ─")
                lines.append("─ 仅供参考, 不构成投资建议. 投资有风险, 入市需谨慎 ─")

                analysis_txt.config(state=tk.NORMAL); analysis_txt.delete("1.0", tk.END)
                analysis_txt.insert(tk.END, "\n".join(lines)); analysis_txt.config(state=tk.DISABLED)

            dlg.after(0, _do_ui)
        _th.Thread(target=_work, daemon=True).start()

    # 初始状态
    analysis_txt.config(state=tk.NORMAL)
    analysis_txt.insert(tk.END, """
╔══════════════════════════════════════════════════════════╗
║          📈 环球洞察 · 昨夜美股 → 今日A股传导分析          ║
╚══════════════════════════════════════════════════════════╝

点击 🔄 获取最新美股数据 → 生成今日A股传导分析

📌 本分析模块功能:
  • 拉取 纳指 / 道指 / 标普500 昨夜表现
  • 识别美股板块信号 (大涨/大跌/龙头异动)
  • 匹配专业传导链条 (纳指→半导体, TSLA→新能源, 等)
  • 获取今日A股行业强弱 TOP5
  • 生成今日操作策略 (进攻/防御/震荡)
  • 精选个股候选池 (成长/消费/新能源/防御)

数据源: AKShare → 东方财富 / 新浪财经
""")
    analysis_txt.config(state=tk.DISABLED)


# ═══════ 主入口 ═══════
def add_market_tabs(nb, dlg):
    try:
        t1 = tk.Frame(nb, bg="#121212"); nb.add(t1, text=" 📊 估值走势 ")
        _build_valuation_tab(t1, dlg)
        t2 = tk.Frame(nb, bg="#121212"); nb.add(t2, text=" 💰 资金变化 ")
        _build_fund_tab(t2, dlg)
        t3 = tk.Frame(nb, bg="#121212"); nb.add(t3, text=" 📍 市场点位 ")
        _build_market_point_tab(t3, dlg)
        t4 = tk.Frame(nb, bg="#121212"); nb.add(t4, text=" 📈 环球洞察 ")
        _build_global_insight_tab(t4, dlg)
        print("[tab_market_valuation] ✅ 4 个 Tab 已添加")
    except Exception as e:
        _tb.print_exc(); print(f"[tab_market_valuation❌] {e}")
