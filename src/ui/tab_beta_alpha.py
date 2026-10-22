"""
📐 β-α 透视 — 散户亏钱防御层

MVP 一期 (FR1 + FR2 + FR4 + 总诊断):
  FR1 市场β体温: 指数涨幅 vs 个股中位数涨幅 (K型分化)
  FR2 我的β暴露: 持仓分蓝筹β vs 题材票
  FR4 指数ETF对照: 买ETF vs 你实际持仓
  总诊断: 散户亏钱风险指数 0-100

设计哲学:
  「普通行情界面问涨了多少，游资界面问钱往哪里去了。」
  「散户界面还要问：我赚的是 β 还是被平均了？我的手管住了没？」
"""
import json
import os
import ssl
import threading
import urllib.request
from datetime import datetime

import numpy as np

from ui.tab_jianlou import _fetch_kline_sina, _fetch_hq_batch, _load_watchlist

# ── 配色 ──
_BG_DEEP = "#121212"; _BG_PANEL = "#1E1E1E"; _BG_CARD = "#2A2A2A"; _BG_TOOLBAR = "#1A1A1A"
_FG_RED = "#FF8A80"; _FG_GREEN = "#69F0AE"; _FG_GOLD = "#FFD54F"; _FG_BLUE = "#90CAF9"
_FG_CYAN = "#80DEEA"; _FG_TEXT = "#E0E0E0"; _FG_DIM = "#888888"; _FG_ORANGE = "#FFB74D"

# ── 指数列表 ──
_INDICES = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
    ("sh000688", "科创50"),
    ("sh000300", "沪深300"),
    ("sz399981", "国证A500"),
]

# ── ETF 对照池 ──
_ETFS = [
    ("sh510300", "沪深300ETF"),
    ("sh510500", "中证500ETF"),
    ("sh512100", "中证1000ETF"),
    ("sh515050", "中证500ETF(A500)"),
    ("sz159915", "创业板ETF"),
    ("sh588000", "科创50ETF"),
]


def _fetch_closes_ytd(sina_code, start_str="2026-01-01", scale=240, datalen=300):
    """拉K线, 返回 (年初收盘, 最新收盘, 涨幅%)"""
    k = _fetch_kline_sina(sina_code, scale=scale, datalen=datalen)
    if not k or len(k["closes"]) < 10:
        return None
    closes = k["closes"]
    dates = k["dates"]
    # 找 start_str 之后第一根
    start_idx = 0
    for i, d in enumerate(dates):
        if d >= start_str:
            start_idx = i; break
    if start_idx >= len(closes) - 1:
        start_idx = 0
    start_p = float(closes[start_idx])
    cur_p = float(closes[-1])
    ret_pct = (cur_p - start_p) / start_p * 100
    return start_p, cur_p, ret_pct, start_idx, len(closes)


def _fetch_index_ytd(sina_code):
    """指数年内涨幅"""
    r = _fetch_closes_ytd(sina_code, "2026-01-01", 240, 300)
    if r:
        return {"sina": sina_code, "start_p": r[0], "cur_p": r[1], "ret": r[2]}
    return None


class BetaAlphaMixin:
    def _show_beta_alpha(self):
        import tkinter as tk
        from tkinter import ttk

        dlg = tk.Toplevel(self.root)
        dlg.title("📐 β-α 透视 · 散户亏钱防御层")
        dlg.geometry("1100x780")
        dlg.configure(bg=_BG_DEEP)
        dlg.transient(self.root)

        # 顶栏
        top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=38)
        top.pack(fill=tk.X); top.pack_propagate(False)
        tk.Label(top, text="📐 β-α 透视", bg=_BG_TOOLBAR, fg=_FG_GOLD,
                 font=("Menlo", 13, "bold")).pack(side=tk.LEFT, padx=12)
        tk.Label(top, text="  「指数涨60%你亏？根因：选股错配 + 行为偏差」",
                 bg=_BG_TOOLBAR, fg=_FG_DIM, font=("", 9)).pack(side=tk.LEFT)

        scan_btn = tk.Button(top, text="🔄一键诊断", bg="#2E7D32", fg="white",
                             font=("", 10, "bold"), relief="flat", padx=14, pady=4)
        scan_btn.pack(side=tk.RIGHT, padx=10)

        status = tk.Label(top, text="⏳ 准备就绪, 点「一键诊断」开始分析...",
                          bg=_BG_TOOLBAR, fg=_FG_DIM, font=("", 9))
        status.pack(side=tk.RIGHT, padx=10)

        # 主体 — ttk Notebook 分 4 个 Tab
        style = ttk.Style(); style.theme_use("clam")
        style.configure("Dark.TNotebook", background=_BG_DEEP, borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background=_BG_PANEL, foreground=_FG_TEXT,
                        padding=[14, 4], font=("", 10))
        style.map("Dark.TNotebook.Tab", background=[("selected", _BG_CARD)],
                  foreground=[("selected", _FG_GOLD)])

        nb = ttk.Notebook(dlg, style="Dark.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 6))

        tab_diag = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_diag, text="🏥总诊断")
        tab_temp = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_temp, text="🌡️市场β体温")
        tab_exp  = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_exp,  text="🎯我的β暴露")
        tab_etf  = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_etf,  text="💹ETF对照")

        # ── 扫描结果容器 ──
        def _clear_tab(parent):
            for w in parent.winfo_children(): w.destroy()

        # ═══════════════════════════════════════════════════════
        #  FR1 · 市场β体温
        # ═══════════════════════════════════════════════════════
        def _render_temp(tab, idx_data, median_ret, up_cnt, down_cnt):
            _clear_tab(tab)
            tk.Label(tab,
                     text="🌡️ 市场β体温 — 少数巨头绑架指数？",
                     bg=_BG_DEEP, fg=_FG_GOLD, font=("", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
            tk.Label(tab,
                     text="指数按市值加权: 10只巨头各涨200%, 90只平/跌, 指数仍涨60%。"
                          "看指数涨 ≠ 多数股票涨。",
                     bg=_BG_DEEP, fg=_FG_DIM, font=("", 9), wraplength=1000,
                     justify="left").pack(anchor="w", padx=12)

            # 双柱图: 每个指数一条 vs 中位数
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig = Figure(figsize=(10, 4.5), facecolor=_BG_DEEP, dpi=100)
            ax = fig.add_axes([0.07, 0.20, 0.88, 0.72], facecolor=_BG_PANEL)

            names = []; idx_rets = []
            for d in idx_data:
                if d:
                    names.append(d["sina"].split(".")[-1])
                    idx_rets.append(d["ret"])
            x = np.arange(len(names))
            bar_w = 0.35
            # 指数柱
            bars_idx = ax.bar(x - bar_w / 2, idx_rets, bar_w,
                              color="#FFD54F", label="指数涨幅", edgecolor="none")
            # 中位数柱 (每条指数对应同一个中位数, 但画成并排)
            med_arr = [median_ret] * len(names)
            bars_med = ax.bar(x + bar_w / 2, med_arr, bar_w,
                              color="#90CAF9" if median_ret >= 0 else "#EF5350",
                              label="全A个股中位数", edgecolor="none")
            # 柱顶数字
            for b, v in zip(bars_idx, idx_rets):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                        f"{v:+.1f}%", ha="center", va="bottom", fontsize=8, color=_FG_GOLD)
            for b, v in zip(bars_med, med_arr):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                        f"{v:+.1f}%", ha="center", va="bottom", fontsize=8,
                        color=_FG_BLUE if median_ret >= 0 else _FG_RED)

            ax.axhline(y=0, color=_FG_DIM, lw=0.6)
            ax.set_xticks(x); ax.set_xticklabels(names, fontsize=9, color=_FG_TEXT)
            ax.set_ylabel("涨幅 %", color=_FG_DIM, fontsize=9)
            ax.tick_params(colors=_FG_DIM)
            for spine in ax.spines.values(): spine.set_color(_FG_DIM)
            ax.legend(loc="upper left", fontsize=9, facecolor=_BG_PANEL,
                      edgecolor=_FG_DIM, labelcolor=_FG_TEXT)

            # K型分化警示
            gap = max(idx_rets) - median_ret
            verdict_color = _FG_RED if gap > 30 else (_FG_ORANGE if gap > 15 else _FG_GREEN)
            verdict_bg = "#3A1B1B" if gap > 30 else ("#3A3A1B" if gap > 15 else "#1B3A1B")
            verdict = (f"📊 K型分化指数 = {gap:.1f}pct\n"
                       f"指数涨 ≠ 个股涨 — {up_cnt}只上涨 vs {down_cnt}只下跌"
                       f"  (跌的比涨的多 = 典型绑架)")
            ax.text(0.98, 0.98, verdict, transform=ax.transAxes, fontsize=8,
                    color=verdict_color, ha="right", va="top",
                    bbox=dict(boxstyle="round,pad=0.4", fc=verdict_bg, ec=verdict_color, alpha=0.9))

            fig.suptitle("📈 2026 YTD 指数 vs 全A个股中位数涨幅",
                         color=_FG_GOLD, fontsize=11, x=0.5)

            canvas = FigureCanvasTkAgg(fig, master=tab)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            canvas.draw()

        # ═══════════════════════════════════════════════════════
        #  FR2 · 我的β暴露
        # ═══════════════════════════════════════════════════════
        def _render_exp(tab, holdings):
            _clear_tab(tab)
            tk.Label(tab,
                     text="🎯 我的β暴露 — 你的票是蓝筹β(绿) 还是 题材票(红)?",
                     bg=_BG_DEEP, fg=_FG_GOLD, font=("", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
            tk.Label(tab,
                     text="蓝筹β(绿): 市值>100亿 + 机构重仓 — 跟指数\n"
                          "题材票(红): 市值<70亿 + 低业绩 + 高换手 — 易跑输\n"
                          "中间(黄): 混合风格",
                     bg=_BG_DEEP, fg=_FG_DIM, font=("", 9),
                     justify="left").pack(anchor="w", padx=12)

            if not holdings:
                tk.Label(tab, text="❌ 无持仓/自选数据", bg=_BG_DEEP, fg=_FG_RED,
                         font=("", 13)).pack(pady=40); return

            # 分类
            blue_chips = []; theme_stocks = []; mid = []
            for h in holdings:
                mktcap = h.get("mktcap", 0)  # 亿
                # 简化分类: 市值是核心
                if mktcap >= 100:
                    blue_chips.append(h)
                elif mktcap <= 70:
                    theme_stocks.append(h)
                else:
                    mid.append(h)

            total = len(holdings)
            pct_blue = len(blue_chips) / total * 100
            pct_theme = len(theme_stocks) / total * 100
            pct_mid = len(mid) / total * 100

            # 饼图
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig = Figure(figsize=(10, 4.5), facecolor=_BG_DEEP, dpi=100)
            ax_pie = fig.add_axes([0.02, 0.18, 0.45, 0.72], facecolor=_BG_DEEP)
            ax_bar = fig.add_axes([0.52, 0.18, 0.46, 0.72], facecolor=_BG_PANEL)

            # 饼
            sizes = [len(blue_chips), len(mid), len(theme_stocks)]
            labels_pie = [f"蓝筹β\n{pct_blue:.0f}%",
                          f"中间型\n{pct_mid:.0f}%",
                          f"题材票\n{pct_theme:.0f}%"]
            colors_pie = ["#66BB6A", "#FFD54F", "#EF5350"]
            if sum(sizes) > 0:
                wedges, texts, autotexts = ax_pie.pie(
                    sizes, labels=labels_pie, colors=colors_pie,
                    autopct="", startangle=90,
                    textprops=dict(color=_FG_TEXT, fontsize=9))
                for t in autotexts: t.set_color("white")
            ax_pie.set_title(f"持仓风格分布 (共{total}只)",
                             color=_FG_GOLD, fontsize=10)

            # 柱状 — 题材票年内涨跌幅 vs 蓝筹
            names_bar = []; rets_bar = []; colors_bar = []
            # 题材票 (最多显示10只, 按市值排序)
            theme_sorted = sorted(theme_stocks, key=lambda x: x.get("mktcap", 999), reverse=True)
            for h in theme_sorted[:10]:
                names_bar.append(h.get("name", "?"))
                rets_bar.append(h.get("ret_ytd", 0))
                colors_bar.append("#EF5350" if h.get("ret_ytd", 0) < 0 else "#FF8A65")
            blue_sorted = sorted(blue_chips, key=lambda x: x.get("ret_ytd", 0), reverse=True)
            for h in blue_sorted[:5]:
                names_bar.append(h.get("name", "?"))
                rets_bar.append(h.get("ret_ytd", 0))
                colors_bar.append("#66BB6A" if h.get("ret_ytd", 0) > 0 else "#4CAF50")

            if names_bar:
                x2 = np.arange(len(names_bar))
                bars = ax_bar.bar(x2, rets_bar, color=colors_bar, edgecolor="none", width=0.7)
                for b, v in zip(bars, rets_bar):
                    ax_bar.text(b.get_x() + b.get_width() / 2, b.get_height(),
                                f"{v:+.0f}", ha="center", va="bottom" if v >= 0 else "top",
                                fontsize=7.5, color=_FG_TEXT)
                ax_bar.axhline(y=0, color=_FG_DIM, lw=0.5)
                ax_bar.set_xticks(x2); ax_bar.set_xticklabels(names_bar, fontsize=7.5,
                                                              color=_FG_TEXT, rotation=35, ha="right")
                ax_bar.set_ylabel("2026 YTD %", color=_FG_DIM, fontsize=9)
                ax_bar.tick_params(colors=_FG_DIM)
                for spine in ax_bar.spines.values(): spine.set_color(_FG_DIM)

            fig.suptitle(f"🎯 持仓β暴露诊断 — 题材票占 {pct_theme:.0f}% {'⚠️ 跑输风险高!' if pct_theme > 50 else '✅ 风格均衡'}",
                         color=_FG_GOLD if pct_theme <= 50 else _FG_RED, fontsize=11, x=0.5)

            canvas = FigureCanvasTkAgg(fig, master=tab)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            canvas.draw()

        # ═══════════════════════════════════════════════════════
        #  FR4 · ETF 对照
        # ═══════════════════════════════════════════════════════
        def _render_etf(tab, idx_ret, holdings):
            _clear_tab(tab)
            tk.Label(tab,
                     text="💹 ETF 对照 — 如果同期买宽基ETF, 你赚多少?",
                     bg=_BG_DEEP, fg=_FG_GOLD, font=("", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
            tk.Label(tab,
                     text="结论: 指数涨60%你却亏, 大概率根因是「选股错配 + 行为偏差」双重叠加。\n"
                          "想稳稳赚指数那60% → 直接买宽基ETF, 别挑个股, 别做T",
                     bg=_BG_DEEP, fg=_FG_DIM, font=("", 9),
                     justify="left").pack(anchor="w", padx=12)

            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig = Figure(figsize=(10, 4.5), facecolor=_BG_DEEP, dpi=100)
            ax = fig.add_axes([0.08, 0.22, 0.86, 0.70], facecolor=_BG_PANEL)

            # 算我的持仓YTD收益 (加权平均)
            my_ret = 0; cnt = 0
            for h in holdings:
                if h.get("ret_ytd") is not None:
                    my_ret += h["ret_ytd"]; cnt += 1
            my_ret = my_ret / cnt if cnt > 0 else 0

            etf_labels = ["沪深300", "中证500", "中证1000", "创业板", "科创50", "我的持仓"]
            # ETF 用指数 YTD 近似
            etf_rets = []
            for sina, _n in [("sh000300", "沪深300"), ("sz399905", "中证500"),
                             ("sh000852", "中证1000"), ("sz399006", "创业板"),
                             ("sh000688", "科创50")]:
                r = _fetch_index_ytd(sina)
                etf_rets.append(r["ret"] if r else 0)
            etf_rets.append(my_ret)

            colors_etf = ["#FFD54F"] * (len(etf_labels) - 1) + ["#EF5350" if my_ret < 0 else "#66BB6A"]

            x = np.arange(len(etf_labels))
            bars = ax.bar(x, etf_rets, color=colors_etf, edgecolor="none", width=0.6)
            for b, v in zip(bars, etf_rets):
                pos = v >= 0
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                        f"{v:+.1f}%", ha="center", va="bottom" if pos else "top",
                        fontsize=9, color="white", fontweight="bold")

            ax.axhline(y=0, color=_FG_DIM, lw=0.6)
            ax.set_xticks(x); ax.set_xticklabels(etf_labels, fontsize=9, color=_FG_TEXT)
            ax.set_ylabel("2026 YTD 涨幅 %", color=_FG_DIM, fontsize=9)
            ax.tick_params(colors=_FG_DIM)
            for spine in ax.spines.values(): spine.set_color(_FG_DIM)

            # 差异对比
            if etf_rets[:-1] and my_ret != 0:
                best_etf = max(etf_rets[:-1])
                gap = best_etf - my_ret
                if gap > 0:
                    msg = f"⚠️ 同期买沪深300赚 {best_etf:+.1f}%, 你的持仓 {my_ret:+.1f}% → 跑输 {gap:.1f}pct"
                    msg_col = _FG_RED; msg_bg = "#3A1B1B"
                else:
                    msg = f"✅ 你的持仓 {my_ret:+.1f}%, 跑赢ETF {abs(gap):.1f}pct → 真α!"
                    msg_col = _FG_GREEN; msg_bg = "#1B3A1B"
                ax.text(0.98, 0.98, msg, transform=ax.transAxes, fontsize=9,
                        color=msg_col, ha="right", va="top",
                        bbox=dict(boxstyle="round,pad=0.5", fc=msg_bg, ec=msg_col, alpha=0.9))

            fig.suptitle("💹 ETF 对照: 同期买宽基 vs 你实际持仓",
                         color=_FG_GOLD, fontsize=11, x=0.5)

            canvas = FigureCanvasTkAgg(fig, master=tab)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            canvas.draw()

        # ═══════════════════════════════════════════════════════
        #  总诊断
        # ═══════════════════════════════════════════════════════
        def _render_diag(tab, idx_data, median_ret, holdings, k_gap):
            _clear_tab(tab)
            tk.Label(tab,
                     text="🏥 β-α 一键诊断 · 散户亏钱风险指数",
                     bg=_BG_DEEP, fg=_FG_GOLD, font=("", 13, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
            tk.Label(tab,
                     text="综合评分 0-100: >60 红牌建议减仓或转ETF",
                     bg=_BG_DEEP, fg=_FG_DIM, font=("", 9)).pack(anchor="w", padx=14)

            # ── 计算三项分 ──
            # β暴露分 (题材票比例越高, 分越高 = 风险越大)
            theme_cnt = sum(1 for h in holdings if h.get("mktcap", 999) <= 70)
            blue_cnt = sum(1 for h in holdings if h.get("mktcap", 0) >= 100)
            total_h = len(holdings) or 1
            beta_exp_score = min(100, int(theme_cnt / total_h * 100))

            # α质量分 (蓝筹正收益 vs 题材负收益)
            blue_rets = [h.get("ret_ytd", 0) for h in holdings if h.get("mktcap", 0) >= 100 and h.get("ret_ytd") is not None]
            theme_rets = [h.get("ret_ytd", 0) for h in holdings if h.get("mktcap", 999) <= 70 and h.get("ret_ytd") is not None]
            blue_avg = np.mean(blue_rets) if blue_rets else 0
            theme_avg = np.mean(theme_rets) if theme_rets else 0
            # 题材跑输越多 → α质量越差
            alpha_q_score = min(100, max(0, int(-theme_avg * 2 + 50)))

            # 行为/环境分 (K型分化大 → 分高 = 风险大)
            behavior_score = min(100, int(k_gap))

            # 综合 (简单平均 + 偏权题材票风险)
            composite = int(beta_exp_score * 0.4 + alpha_q_score * 0.3 + behavior_score * 0.3)

            # ── 画仪表盘 ──
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig = Figure(figsize=(10.5, 6.0), facecolor=_BG_DEEP, dpi=100)

            # 仪表盘 (左上)
            ax_g = fig.add_axes([0.05, 0.45, 0.35, 0.50], facecolor=_BG_DEEP, polar=True)
            theta = np.linspace(np.pi, 2 * np.pi, 100)
            # 背景圈
            ax_g.plot(theta, np.full_like(theta, 0.9), color=_BG_CARD, lw=18)
            # 风险区间上色
            for lo, hi, col in [(0, 30, "#1B3A1B"), (30, 60, "#3A3A1B"), (60, 100, "#3A1B1B")]:
                t_lo = np.pi + (lo / 100) * np.pi
                t_hi = np.pi + (hi / 100) * np.pi
                t = np.linspace(t_lo, t_hi, 30)
                ax_g.plot(t, np.full_like(t, 0.9), color=col, lw=18)
            # 当前值 (粗线)
            cur_theta = np.pi + (composite / 100) * np.pi
            ax_g.plot([cur_theta, cur_theta], [0.7, 0.95], color=_FG_GOLD, lw=4)
            ax_g.set_ylim(0, 1); ax_g.set_yticks([]); ax_g.set_xticks([])
            ax_g.spines["polar"].set_color(_BG_DEEP)
            ax_g.text(0.5, 0.15, f"{composite}", transform=ax_g.transAxes,
                      fontsize=36, fontweight="bold",
                      color=_FG_RED if composite > 60 else (_FG_ORANGE if composite > 30 else _FG_GREEN),
                      ha="center", va="center")
            ax_g.text(0.5, -0.05, "风险指数", transform=ax_g.transAxes,
                      fontsize=10, color=_FG_DIM, ha="center")
            ax_g.text(0.5, -0.18,
                      "红牌 → 减仓/转ETF" if composite > 60 else
                      ("黄牌 → 观察" if composite > 30 else "✅ 健康"),
                      transform=ax_g.transAxes,
                      fontsize=10,
                      color=_FG_RED if composite > 60 else (_FG_ORANGE if composite > 30 else _FG_GREEN),
                      ha="center")

            # 三项分柱状 (右上)
            ax_b = fig.add_axes([0.48, 0.45, 0.48, 0.50], facecolor=_BG_PANEL)
            cats = ["β暴露分", "α质量分", "行为/环境"]
            vals = [beta_exp_score, alpha_q_score, behavior_score]
            cols = []
            for v in vals:
                if v > 60: cols.append("#EF5350")
                elif v > 30: cols.append("#FFD54F")
                else: cols.append("#66BB6A")
            x = np.arange(3)
            bars = ax_b.bar(x, vals, color=cols, edgecolor="none", width=0.5)
            for b, v in zip(bars, vals):
                ax_b.text(b.get_x() + b.get_width() / 2, b.get_height() + 2,
                          str(v), ha="center", fontsize=11, fontweight="bold",
                          color=_FG_TEXT)
            ax_b.set_xticks(x); ax_b.set_xticklabels(cats, fontsize=9, color=_FG_TEXT)
            ax_b.set_ylim(0, 110); ax_b.set_ylabel("分越高 = 风险越大", color=_FG_DIM, fontsize=8)
            ax_b.tick_params(colors=_FG_DIM)
            for spine in ax_b.spines.values(): spine.set_color(_FG_DIM)
            ax_b.axhline(y=60, color=_FG_RED, lw=0.5, ls="--", alpha=0.5)
            ax_b.axhline(y=30, color=_FG_GREEN, lw=0.5, ls="--", alpha=0.5)

            # 诊断要点 (底部文字)
            ax_t = fig.add_axes([0.05, 0.05, 0.92, 0.35], facecolor=_BG_PANEL)
            ax_t.axis("off")
            lines = [
                f"📊 β暴露分 {beta_exp_score}/100 → 题材票 {theme_cnt}/{total_h}只, 蓝筹β {blue_cnt}/{total_h}只",
                f"📈 α质量分 {alpha_q_score}/100 → 蓝筹YTD均 {blue_avg:+.1f}%, 题材YTD均 {theme_avg:+.1f}%",
                f"🌡️ 行为/环境分 {behavior_score}/100 → K型分化 {k_gap:.1f}pct (指数vs中位数)",
                f"",
            ]
            if composite > 60:
                lines += [f"🔴 综合风险指数 {composite} → 红牌!"]
                lines += [f"   建议: ① 逐步减仓题材票 ② 转配沪深300ETF/中证A500ETF ③ 等市场风格切换再回来"]
            elif composite > 30:
                lines += [f"🟡 综合风险指数 {composite} → 黄牌"]
                lines += [f"   建议: 控制题材票仓位在40%以内, 新增仓位优先蓝筹/ETF"]
            else:
                lines += [f"🟢 综合风险指数 {composite} → 健康"]
                lines += [f"   建议: 保持当前配置, 做好止盈止损"]

            for i, ln in enumerate(lines):
                c = _FG_GOLD if i == 0 else (_FG_RED if composite > 60 else (_FG_ORANGE if composite > 30 else _FG_GREEN))
                ax_t.text(0.02, 0.92 - i * 0.12, ln, transform=ax_t.transAxes,
                          fontsize=10, color=_FG_TEXT if i < 4 else c,
                          va="top", ha="left", family="Menlo")

            canvas = FigureCanvasTkAgg(fig, master=tab)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            canvas.draw()

        # ── 一键诊断流程 ──
        def _run_diag():
            scan_btn.config(state=tk.DISABLED, text="⏳诊断中...")
            status.config(text="⏳ 拉指数YTD + 扫持仓...", fg=_FG_DIM)

            def _bg():
                # 1. 指数YTD
                idx_res = []
                for sina, _n in _INDICES:
                    idx_res.append(_fetch_index_ytd(sina))

                # 2. 拉自选股 (持仓+龙头+资讯)
                watchlist = _load_watchlist()
                sina_codes = [s for _, s, _ in watchlist]
                # 3. 实时行情
                hq_map = _fetch_hq_batch(sina_codes)

                # 4. 算每只YTD + 近似市值 (用现价*流通股估算太复杂, 用市值字段)
                # 新浪 hq 字段里有 mktcap? —— 没有, 但我们可以用 hq_map + 日线YTD
                holdings = []
                for name, sina, tag in watchlist:
                    hq = hq_map.get(sina, {})
                    cur = float(hq.get("price", hq.get("cur", 0)))
                    vol = float(hq.get("volume", 0))
                    # YTD (用日线)
                    k_ret = _fetch_closes_ytd(sina, "2026-01-01", 240, 300)
                    ret_ytd = k_ret[2] if k_ret else None
                    # 近似市值估算 (简化): 成交额/换手率 ≈ 市值, 但我们没换手率
                    # 用 tag + 名字里的关键词粗分:
                    # 龙头/主力 → 蓝筹候选; 资讯 → 题材候选; 持仓看名字
                    mktcap = 50  # 默认中间
                    if tag == "龙头": mktcap = 200
                    elif tag == "持仓": mktcap = 100
                    elif tag == "资讯": mktcap = 50
                    elif tag == "基金": mktcap = 150
                    holdings.append({
                    "name": name, "sina": sina, "tag": tag,
                    "cur": cur, "volume": vol,
                    "ret_ytd": ret_ytd, "mktcap": mktcap,
                })

                # 5. 中位数 (过滤 None)
                rets_valid = [h["ret_ytd"] for h in holdings if h.get("ret_ytd") is not None]
                median_ret = float(np.median(rets_valid)) if rets_valid else 0
                up_cnt = sum(1 for r in rets_valid if r > 0)
                down_cnt = sum(1 for r in rets_valid if r <= 0)

                # 🆕 统一兜底: ret_ytd 为 None 的全部设为 0 —— 防止 NoneType 比较
                for h in holdings:
                    if h.get("ret_ytd") is None:
                        h["ret_ytd"] = 0.0

                # 6. K型分化 = 最大指数涨幅 - 个股中位数
                valid_idx = [d for d in idx_res if d]
                max_idx_ret = max(d["ret"] for d in valid_idx) if valid_idx else 0
                k_gap = max_idx_ret - median_ret

                # 切回主线程渲染
                def _ui():
                    try:
                        _render_temp(tab_temp, idx_res, median_ret, up_cnt, down_cnt)
                        _render_exp(tab_exp, holdings)
                        hs300 = next((d for d in idx_res if d and "000300" in d["sina"]), None)
                        hs300_ret = hs300["ret"] if hs300 else 0
                        _render_etf(tab_etf, hs300_ret, holdings)
                        _render_diag(tab_diag, idx_res, median_ret, holdings, k_gap)
                        status.config(
                            text=f"✅ 诊断完成  中位数{median_ret:+.1f}%  K型{k_gap:.1f}pct  "
                                 f"题材票{sum(1 for h in holdings if h['mktcap']<=70)}/{len(holdings)}",
                            fg=_FG_GREEN)
                    except Exception as _e:
                        import traceback
                        tb = traceback.format_exc()
                        print(f"[β-α] 渲染异常:\n{tb}", flush=True)
                        # 状态栏显示前100字符
                        short = str(_e)[:80]
                        status.config(text=f"❌ 渲染异常: {short}", fg=_FG_RED)
                        # 主窗口也显示
                        tk.Label(tab_diag,
                                 text=f"❌ 渲染异常\n\n{tb}",
                                 bg=_BG_DEEP, fg=_FG_RED,
                                 font=("Menlo", 9), justify="left").pack(anchor="w", padx=12, pady=12)

                    scan_btn.config(state=tk.NORMAL, text="🔄一键诊断")

                dlg.after(0, _ui)

            threading.Thread(target=_bg, daemon=True).start()

        scan_btn.config(command=_run_diag)
        dlg.after(200, _run_diag)


__all__ = ["BetaAlphaMixin"]
