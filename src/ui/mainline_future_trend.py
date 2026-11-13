# -*- coding: utf-8 -*-
"""
📈 后续走势分析 Tab —— 三维度 (短/中/长) 走势判断
---------------------------------------------------
在「🔥主线·资金」弹窗 Notebook 里新增 Tab3。
"""

import tkinter as tk
from tkinter import ttk
import threading
import datetime


def _build_future_trend_tab(nb_notebook, root=None):
    """🆕 在给定 Notebook 里加 Tab: 📈后续走势"""
    tab = tk.Frame(nb_notebook, bg="#FAFAFA")
    nb_notebook.add(tab, text="  📈 后续走势  ")

    # Banner
    banner = tk.Frame(tab, bg="#1565C0", height=48)
    banner.pack(fill=tk.X, padx=6, pady=(6, 4))
    banner.pack_propagate(False)
    tk.Label(banner, text="📈 A股后续走势研判 · 三维度分析",
             font=("Microsoft YaHei", 12, "bold"),
             bg="#1565C0", fg="white").pack(side=tk.LEFT, padx=14)
    _status = tk.Label(banner, text="⏳ 点 🔄 拉取数据开始分析...",
                       font=("", 10), bg="#1565C0", fg="#BBDEFB")
    _status.pack(side=tk.LEFT, padx=10)
    _refresh_btn = tk.Button(banner, text="🔄 拉取数据分析", bg="#FFD54F", fg="#5D4037",
                              font=("", 10, "bold"), relief=tk.FLAT, padx=10, cursor="hand2")
    _refresh_btn.pack(side=tk.RIGHT, padx=10, pady=8)

    # ═══════════════════════════════════════════════════════════
    # 三个大卡片: 短期 / 中期 / 长期
    # ═══════════════════════════════════════════════════════════
    cards_row = tk.Frame(tab, bg="#FAFAFA")
    cards_row.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    card_frame_short = _make_card(cards_row, "一、短期 (1-5天)", "#FF6F00",
                                   "#FFF3E0", "#FF9800")
    card_frame_short.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
    txt_short = _make_scroll_text(card_frame_short, 9)

    card_frame_mid = _make_card(cards_row, "二、中期 (1-3月)", "#7B1FA2",
                                 "#F3E5F5", "#9C27B0")
    card_frame_mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
    txt_mid = _make_scroll_text(card_frame_mid, 9)

    card_frame_long = _make_card(cards_row, "三、长期 (1年+)", "#00695C",
                                  "#E0F2F1", "#26A69A")
    card_frame_long.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
    txt_long = _make_scroll_text(card_frame_long, 9)

    # 底部: 操作建议 + 风险提示
    bottom_row = tk.Frame(tab, bg="#FAFAFA")
    bottom_row.pack(fill=tk.X, padx=6, pady=(2, 6))
    card_op = _make_card(bottom_row, "💼 操作建议 (结合当前市场)", "#1565C0",
                          "#E3F2FD", "#42A5F5")
    card_op.pack(fill=tk.X)
    txt_op = _make_scroll_text(card_op, 10)

    card_risk = _make_card(bottom_row, "⚠️ 风险控制 & 关键提醒", "#C62828",
                            "#FFEBEE", "#EF5350")
    card_risk.pack(fill=tk.X, pady=(4, 0))
    txt_risk = _make_scroll_text(card_risk, 10)

    # 存到 tab 供分析函数写回
    tab_refs = dict(
        status=_status, refresh_btn=_refresh_btn,
        txt_short=txt_short, txt_mid=txt_mid, txt_long=txt_long,
        txt_op=txt_op, txt_risk=txt_risk,
    )
    tab._refs = tab_refs
    tab._root = root or nb_notebook.winfo_toplevel()

    # 🔄 绑定刷新按钮
    _refresh_btn.config(command=lambda: _start_future_trend_analysis(tab))

    # ⚡ 自动加载一次 (后台线程)
    tab.after(300, lambda: _start_future_trend_analysis(tab))

    return tab


def _make_card(parent, title, fg_title, bg_inner, accent_color):
    """建一个带标题 + 内框的卡片"""
    card = tk.Frame(parent, bg=bg_inner, bd=0, highlightthickness=1,
                    highlightbackground=accent_color)
    head = tk.Frame(card, bg=accent_color, height=26)
    head.pack(fill=tk.X); head.pack_propagate(False)
    tk.Label(head, text=title, font=("Microsoft YaHei", 10, "bold"),
             bg=accent_color, fg="white").pack(side=tk.LEFT, padx=10)
    inner = tk.Frame(card, bg=bg_inner)
    inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    return inner


def _make_scroll_text(parent, font_size=9):
    from tkinter import scrolledtext
    st = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("", font_size),
                                   bg=parent["background"], fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=6, pady=4,
                                   height=12)
    st.pack(fill=tk.BOTH, expand=True)
    st.tag_configure("title", font=("", font_size + 1, "bold"))
    st.tag_configure("up", foreground="#C62828", font=("", font_size, "bold"))
    st.tag_configure("dn", foreground="#2E7D32", font=("", font_size, "bold"))
    st.tag_configure("warn", foreground="#E65100", font=("", font_size, "bold"))
    st.tag_configure("ok", foreground="#1565C0", font=("", font_size, "bold"))
    return st


def _start_future_trend_analysis(tab):
    """🔄 启动后台分析"""
    refs = tab._refs
    refs["refresh_btn"].config(state=tk.DISABLED, text="🔄 拉取中...")
    refs["status"].config(text="⏳ 正在拉取市场数据 (可能 10-30秒)...", fg="#FFCCBC")
    # 清空
    for k in ("txt_short", "txt_mid", "txt_long", "txt_op", "txt_risk"):
        refs[k].config(state=tk.NORMAL); refs[k].delete("1.0", tk.END)

    threading.Thread(target=_run_analysis_worker, args=(tab,), daemon=True).start()


def _run_analysis_worker(tab):
    refs = tab._refs
    try:
        # ========== 1. 拉数据 ==========
        _safe_status(tab, "⏳ 拉取上证日线 + 均线...")
        sh_df = _fetch_sh_index_days()

        _safe_status(tab, "⏳ 拉取 ETF 资金流向...")
        etf_flow = _fetch_etf_main_flow()

        _safe_status(tab, "⏳ 拉取涨停家数 + 广度...")
        breadth = _fetch_market_breadth()

        _safe_status(tab, "⏳ 拉取北向资金...")
        north = _fetch_north_flow()

        _safe_status(tab, "⏳ 拉取估值分位...")
        valuation = _fetch_valuation_percentile()

        # ========== 2. 分析 ==========
        short_text = _analyze_short_term(sh_df, etf_flow, breadth, north)
        mid_text = _analyze_mid_term(sh_df, valuation, breadth)
        long_text = _analyze_long_term(sh_df, etf_flow, north)
        op_text, risk_text = _make_action_advice(sh_df, etf_flow, breadth, valuation)

        # ========== 3. 写回 UI (主线程) ==========
        def _write_all():
            refs["txt_short"].config(state=tk.NORMAL)
            refs["txt_short"].insert(tk.END, short_text); refs["txt_short"].config(state=tk.DISABLED)
            refs["txt_mid"].config(state=tk.NORMAL)
            refs["txt_mid"].insert(tk.END, mid_text); refs["txt_mid"].config(state=tk.DISABLED)
            refs["txt_long"].config(state=tk.NORMAL)
            refs["txt_long"].insert(tk.END, long_text); refs["txt_long"].config(state=tk.DISABLED)
            refs["txt_op"].config(state=tk.NORMAL)
            refs["txt_op"].insert(tk.END, op_text); refs["txt_op"].config(state=tk.DISABLED)
            refs["txt_risk"].config(state=tk.NORMAL)
            refs["txt_risk"].insert(tk.END, risk_text); refs["txt_risk"].config(state=tk.DISABLED)
            refs["status"].config(text=f"✅ 分析完成 · {datetime.datetime.now().strftime('%H:%M:%S')}", fg="#C8E6C9")
            refs["refresh_btn"].config(state=tk.NORMAL, text="🔄 重新分析")

        tab._root.after(0, _write_all)

    except Exception as _e:
        import traceback
        traceback.print_exc()
        def _on_err():
            refs["status"].config(text=f"❌ 分析失败: {_e}", fg="#FFCDD2")
            refs["refresh_btn"].config(state=tk.NORMAL, text="🔄 重试")
        tab._root.after(0, _on_err)


def _safe_status(tab, msg):
    tab._root.after(0, lambda: tab._refs["status"].config(text=msg, fg="#FFCCBC"))


# ═══════════════════════════════════════════════════════════
# 数据获取函数 (独立, 失败返回 None/空, 不抛)
# ═══════════════════════════════════════════════════════════

def _fetch_sh_index_days(days=260):
    """上证指数日线 (含收盘/量能)"""
    try:
        from ui._akshare_fetcher import fetch_index_daily
        df = fetch_index_daily("sh000001", days=days)
        if df is None or len(df) == 0:
            return None
        return df
    except Exception as e:
        print(f"[后续走势] 上证日线失败: {e}")
        return None


def _fetch_etf_main_flow():
    """核心 ETF (沪深300/科创50/创业板) 主力资金流向"""
    result = {}
    try:
        import akshare as ak
        # ETF 实时行情 (沪深300/科创50/创业板ETF)
        symbols = {"沪深300ETF": "510300", "科创50ETF": "588000", "创业板ETF": "159915"}
        for name, code in symbols.items():
            try:
                df = ak.fund_etf_spot_em()
                if df is not None and len(df) > 0:
                    row = df[df["代码"] == code]
                    if len(row) > 0:
                        r = row.iloc[0]
                        result[name] = {
                            "price": float(r.get("最新价", 0) or 0),
                            "pct": float(r.get("涨跌幅", 0) or 0),
                            "volume_yi": float(r.get("成交额", 0) or 0) / 1e8,
                        }
            except Exception:
                pass
        # ETF 主力资金流
        try:
            flow_df = ak.stock_individual_fund_flow(stock="510300", market="sh")
            if flow_df is not None and len(flow_df) > 0:
                result["沪深300ETF_主力5日"] = flow_df.tail(5)["主力净流入-净额"].tolist()
                result["沪深300ETF_主力20日"] = flow_df.tail(20)["主力净流入-净额"].sum()
        except Exception:
            pass
    except Exception as e:
        print(f"[后续走势] ETF 资金流失败: {e}")
    return result


def _fetch_market_breadth():
    """涨停家数 / 上涨下跌 / 成交额 — 优先 DB, 兜底 akshare"""
    result = {}
    # 1) 从 sentiment_history DB 拿涨跌家数
    try:
        import sqlite3, os
        db_path = os.path.join(os.path.expanduser("~"), ".stockyidong_data", "stock_analysis.db")
        if not os.path.exists(db_path):
            db_path = "data/stock_analysis.db"
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            # 列名: m2_up / m2_down / m3_count(涨停) / m4_count(跌停) / snapshot_date
            cur.execute("SELECT m2_up, m2_down, m3_count, m4_count FROM sentiment_history ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                result["up"] = int(row[0] or 0)
                result["dn"] = int(row[1] or 0)
                result["limit_up"] = int(row[2] or 0)
                result["limit_dn"] = int(row[3] or 0)
            conn.close()
    except Exception as e:
        print(f"[后续走势] 广度DB读取失败: {e}")

    # 2) 从上证日线估算成交额 (volume 手 × close ≈ 元)
    try:
        from ui._akshare_fetcher import fetch_index_daily
        df = fetch_index_daily("sh000001", days=5)
        if df is not None and len(df) > 0:
            _last = df.iloc[-1]
            _vol = float(_last.get("volume", 0) or 0)  # 手
            _close = float(_last.get("close", 0) or 0)
            if _vol > 0 and _close > 0:
                # volume 是股数 × close ≈ 元 → /1e8 = 亿
                result["turnover_yi"] = round(_vol * _close / 1e8, 0)
    except Exception as e:
        print(f"[后续走势] 成交额估算失败: {e}")

    # 3) 如果 DB 没数据, 兜底用 akshare 涨跌家数
    if not result.get("up"):
        try:
            import akshare as ak
            spot = ak.stock_zh_a_spot_em()
            if spot is not None and len(spot) > 0:
                up = len(spot[spot["涨跌幅"] > 0])
                dn = len(spot[spot["涨跌幅"] < 0])
                result["up"] = up; result["dn"] = dn
                # 涨停 = 涨幅 >= 9.5%
                zt = len(spot[spot["涨跌幅"] >= 9.5])
                zd = len(spot[spot["涨跌幅"] <= -9.5])
                result["limit_up"] = zt; result["limit_dn"] = zd
                result["turnover_yi"] = round(float(spot["成交额"].sum() or 0) / 1e8, 0)
        except Exception as e2:
            print(f"[后续走势] 广度akshare兜底也失败: {e2}")

    return result


def _fetch_north_flow():
    """北向资金净流入 — 沪股通 + 深股通 合计"""
    result = {}
    try:
        import akshare as ak
        import pandas as pd
        # 沪深港通 沪股通 + 深股通 今日净买额
        total_today = 0.0; total_5d = 0.0; _has = False
        for sym in ["沪股通", "深股通"]:
            try:
                df = ak.stock_hsgt_hist_em(symbol=sym)
                if df is not None and len(df) > 0:
                    col = "当日成交净买额"
                    vals = pd.to_numeric(df[col], errors="coerce").dropna()
                    if len(vals) >= 1:
                        total_today += float(vals.iloc[-1])
                        _has = True
                    if len(vals) >= 5:
                        total_5d += float(vals.tail(5).sum())
            except Exception:
                pass
        if _has:
            result["north_today"] = round(total_today / 1e8, 2)
            result["north_5d"] = round(total_5d / 1e8, 2)
    except Exception as e:
        print(f"[后续走势] 北向资金失败: {e}")
    return result


def _fetch_valuation_percentile():
    """沪深300估值分位 — 用 akstock_zh_index_value_csindex"""
    result = {}
    try:
        import ssl, urllib.request
        # 关闭 SSL 验证 (本地环境证书链问题)
        ssl._create_default_https_context = ssl._create_unverified_context
        import akshare as ak
        df = ak.stock_zh_index_value_csindex(symbol="000300")
        if df is not None and len(df) > 0:
            # 可能的列: 日期/市盈率/静态市盈率/TTM市盈率
            _pe_col = None
            for _c in df.columns:
                if 'TTM' in str(_c) or ('市盈' in str(_c) and 'TTM' in str(df[_c].name if hasattr(df[_c], 'name') else '')):
                    _pe_col = _c; break
            if _pe_col is None:
                for _c in df.columns:
                    if 'TTM' in str(_c): _pe_col = _c; break
            if _pe_col is None:
                # 用最后一列数值
                _pe_col = df.select_dtypes(include=['float64', 'int64']).columns[-1]
            hist = df[_pe_col].dropna().astype(float).tolist()
            if hist:
                latest = hist[-1]
                # 近3年分位 → 最近 750 天
                _3y = hist[-750:] if len(hist) >= 750 else hist
                below = sum(1 for v in _3y if v <= latest)
                result["hs300_pe"] = round(latest, 2)
                result["hs300_pe_pct"] = round(below / len(_3y) * 100, 1)
                print(f"[后续走势] ✅ 沪深300 PE={latest:.1f}, 近3年分位 {result['hs300_pe_pct']:.0f}%")
    except Exception as e:
        print(f"[后续走势] 估值分位失败: {e}")
    return result


# ═══════════════════════════════════════════════════════════
# 分析函数 —— 根据数据输出中文判断文本
# ═══════════════════════════════════════════════════════════

def _sma(series, n):
    """简单均线"""
    try:
        if series is None or len(series) < n:
            return None
        return sum(series[-n:]) / n
    except:
        return None


def _analyze_short_term(sh_df, etf, breadth, north):
    """短期 (1-5天) — 资金情绪"""
    lines = ["📅 短期研判 (1-5天)\n"]
    lines.append("━" * 28)

    # 1) ETF 资金流
    lines.append("\n🔍 ETF 主力资金流向 (核心锚点):")
    _h300_etf = etf.get("沪深300ETF", {})
    if _h300_etf:
        _pct = _h300_etf.get("pct", 0)
        _vol = _h300_etf.get("volume_yi", 0)
        lines.append(f"  📌 沪深300ETF: 涨跌 {_pct:+.2f}% · 成交 {_vol:.1f}亿")
        # 20 日累计
        _flow20 = etf.get("沪深300ETF_主力20日", 0)
        if _flow20:
            _flow20_yi = _flow20 / 1e8
            if _flow20_yi > 50:
                lines.append(f"  🟢 20日主力净流入 {_flow20_yi:.0f}亿 → 资金持续回流, 短期企稳概率大")
            elif _flow20_yi < -30:
                lines.append(f"  🔴 20日主力净流出 {_flow20_yi:.0f}亿 → 资金撤退, 反弹易夭折")
            else:
                lines.append(f"  🟡 20日净流入 {_flow20_yi:.0f}亿 → 多空博弈, 震荡为主")
    else:
        lines.append("  ⚠️ ETF 数据暂不可用 (akshare 接口可能限流)")

    # 2) 成交量验证
    lines.append("\n🔍 成交量 (验证承接力):")
    _to = breadth.get("turnover_yi", 0)
    if _to > 0:
        if _to < 4000:
            lines.append(f"  🟡 今日成交 {_to:.0f}亿 (半日级低量) → 无增量资金, 冲高易触发获利盘兑现")
        elif _to < 7000:
            lines.append(f"  🟢 今日成交 {_to:.0f}亿 (正常量) → 承接尚可, 观察指数是否同步上涨")
        else:
            lines.append(f"  🔴 今日成交 {_to:.0f}亿 (天量) → 放量滞涨警惕主力出货, 放量上涨则可能延续")
    else:
        lines.append("  ⚠️ 成交额数据暂不可用")

    # 3) 情绪广度
    lines.append("\n🔍 情绪广度 (涨停/涨跌家数):")
    _up = breadth.get("up", 0); _dn = breadth.get("dn", 0)
    _zup = breadth.get("limit_up", 0); _zdn = breadth.get("limit_dn", 0)
    if _up + _dn > 0:
        _pct_up = _up / (_up + _dn) * 100
        if _pct_up < 25:
            lines.append(f"  🔴 上涨 {_up} vs 下跌 {_dn} ({_pct_up:.0f}%红盘) → 情绪极弱, 观望为主")
        elif _pct_up < 45:
            lines.append(f"  🟡 上涨 {_up} vs 下跌 {_dn} ({_pct_up:.0f}%红盘) → 震荡偏弱, 热点轮动快")
        else:
            lines.append(f"  🟢 上涨 {_up} vs 下跌 {_dn} ({_pct_up:.0f}%红盘) → 情绪尚可, 可轻仓参与")
    if _zup > 0 or _zdn > 0:
        lines.append(f"  🎯 涨停 {_zup} · 跌停 {_zdn} → {'情绪亢奋' if _zup > 60 else '情绪一般'}")

    # 4) 北向资金
    lines.append("\n🔍 北向资金 (外资风向标):")
    _n5 = north.get("north_5d", 0); _nt = north.get("north_today", 0)
    if _nt or _n5:
        _n5_billion = _n5
        if _n5_billion > 100:
            lines.append(f"  🟢 今日 {_nt:+.1f}亿 · 5日累计 {_n5_billion:+.0f}亿 → 外资持续加仓, 利好")
        elif _n5_billion < -50:
            lines.append(f"  🔴 今日 {_nt:+.1f}亿 · 5日累计 {_n5_billion:+.0f}亿 → 外资撤退, 谨慎")
        else:
            lines.append(f"  🟡 今日 {_nt:+.1f}亿 · 5日累计 {_n5_billion:+.0f}亿 → 观望态度")
    else:
        lines.append("  ⚠️ 北向资金数据暂不可用")

    lines.append("\n💡 短期结论: 震荡节奏为主, 优先用 「ETF流向 + 成交量」 过滤噪音")
    return "\n".join(lines)


def _analyze_mid_term(sh_df, valuation, breadth):
    """中期 (1-3月) — 技术结构 + 基本面"""
    lines = ["📅 中期研判 (1-3月)\n"]
    lines.append("━" * 28)

    # 1) 均线结构
    lines.append("\n🔍 均线与技术结构:")
    if sh_df is not None and len(sh_df) > 60:
        closes = sh_df["close"].astype(float).tolist()
        ma5 = _sma(closes, 5)
        ma10 = _sma(closes, 10)
        ma20 = _sma(closes, 20)
        ma60 = _sma(closes, 60)
        ma250 = _sma(closes, min(250, len(closes)))
        last = closes[-1]

        lines.append(f"  📌 上证当前: {last:.1f}")
        for name, val in [("MA5", ma5), ("MA20", ma20), ("MA60", ma60), ("MA250", ma250)]:
            if val:
                _pos = "↑站上" if last > val else "↓跌破"
                lines.append(f"    {name}: {val:.1f} · {_pos}")

        # 20/60日均线判断
        if ma20 and ma60:
            if last > ma20 and ma20 > ma60:
                lines.append(f"  🟢 多头排列 (价>MA20>MA60) → 中期趋势向上, 震荡上沿拓展")
            elif last < ma20 and ma20 < ma60:
                lines.append(f"  🔴 空头排列 (价<MA20<MA60) → 中期趋势向下, 回踩MA60支撑后观察")
            else:
                lines.append(f"  🟡 均线纠缠 (MA20={ma20:.0f}, MA60={ma60:.0f}) → 震荡格局, 等待方向选择")
        if ma60 and ma250:
            if ma60 > ma250:
                lines.append(f"  🟢 MA60 在 MA250 上方 → 中期趋势偏多 (牛熊线之上)")
            else:
                lines.append(f"  🟡 MA60 在 MA250 下方 → 长期趋势仍偏弱, 反弹需站稳MA250")
    else:
        lines.append("  ⚠️ 日线数据不足 60 天, 均线分析暂不可用")

    # 2) 估值分位
    lines.append("\n🔍 估值安全边际:")
    _pe = valuation.get("hs300_pe", 0); _pct = valuation.get("hs300_pe_pct", 0)
    if _pe and _pct:
        if _pct < 20:
            lines.append(f"  🟢 沪深300 PE={_pe:.1f} (近3年 {_pct:.0f}%分位) → 底部区域, 安全边际充足")
        elif _pct < 50:
            lines.append(f"  🟡 沪深300 PE={_pe:.1f} (近3年 {_pct:.0f}%分位) → 中低位, 估值合理")
        else:
            lines.append(f"  🔴 沪深300 PE={_pe:.1f} (近3年 {_pct:.0f}%分位) → 偏高, 注意回调风险")
    else:
        lines.append("  ⚠️ 估值分位数据暂不可用")
    lines.append("  📌 存款市值比 (居民存款/A股市值 > 2.5 为历史底部) → 需手动观察")

    lines.append("\n💡 中期结论: 技术面定方向, 估值定仓位, 盈利拐点 (三季报后) 是关键验证信号")
    return "\n".join(lines)


def _analyze_long_term(sh_df, etf, north):
    """长期 (1年+) — 宏观政策 + 资金周期"""
    lines = ["📅 长期研判 (1年+)\n"]
    lines.append("━" * 28)

    lines.append("\n🔍 宏观 & 政策环境:")
    lines.append("  📌 核心观察点 (需手动跟踪):")
    lines.append("     ① 经济复苏强度: 社零/地产数据是否见底回升")
    lines.append("     ② 流动性: MLF/LPR 是否继续宽松降准")
    lines.append("     ③ 产业政策: 科技/高端制造是否有持续政策支持")
    lines.append("     ④ 国际环境: 美联储政策/中美关系是否边际改善")

    lines.append("\n🔍 资金周期信号:")
    # ETF 20日累计
    _flow20 = etf.get("沪深300ETF_主力20日", 0)
    if _flow20:
        _flow20_billion = _flow20 / 1e8
        if _flow20_billion > 6000:
            lines.append(f"  🟢 ETF 主力20日净流入 {_flow20_billion:.0f}亿 → 底部建仓信号 (如前期2024年)")
        elif _flow20_billion > 2000:
            lines.append(f"  🟡 ETF 主力20日净流入 {_flow20_billion:.0f}亿 → 资金温和入场")
        elif _flow20_billion < -3000:
            lines.append(f"  🔴 ETF 主力20日净流出 {abs(_flow20_billion):.0f}亿 → 高位兑现, 警惕趋势转弱")
        else:
            lines.append(f"  🟡 ETF 20日净流入 {_flow20_billion:.0f}亿 → 存量博弈, 无明显建仓/兑现")
    else:
        lines.append("  🟡 ETF 资金周期数据不足 → 需长期跟踪累计流向")

    # 北向长期
    _n5 = north.get("north_5d", 0)
    if _n5 < -100:
        lines.append(f"  🔴 北向5日净流出 {abs(_n5):.0f}亿 → 外资撤退, 长期资金信心不足")
    elif _n5 > 100:
        lines.append(f"  🟢 北向5日净流入 {_n5:.0f}亿 → 外资加仓, 长期看好")

    lines.append("\n💡 长期结论: 政策宽松 + 经济回暖 + ETF持续净流入 → 慢牛基础; 否则震荡寻底")
    return "\n".join(lines)


def _make_action_advice(sh_df, etf, breadth, valuation):
    """操作建议 + 风险提示"""
    op = ["💼 操作建议 (结合当前市场环境)\n"]
    op.append("━" * 28)

    # 判断当前市况
    regime = "震荡市"
    reason = []
    if sh_df is not None and len(sh_df) > 60:
        closes = sh_df["close"].astype(float).tolist()
        last = closes[-1]
        ma20 = _sma(closes, 20); ma60 = _sma(closes, 60)
        if ma20 and ma60:
            if last > ma20 > ma60:
                regime = "趋势市 (多头排列)"; reason.append("站上MA20且MA20>MA60")
            elif last < ma60:
                regime = "弱势市 (跌破MA60)"; reason.append("跌破MA60支撑")
            else:
                reason.append("MA20附近震荡")

    op.append(f"\n🎯 当前判断: {regime}")
    if reason:
        op.append(f"   依据: {', '.join(reason)}")

    op.append("\n📋 操作策略:")
    if "震荡" in regime:
        op.append("  ✅ 轻仓波段操作为主")
        op.append("  ✅ 回调至 MA60 + 缩量企稳 → 分批低吸")
        op.append("  ✅ 冲高至 MA20 + 放量滞涨 → 分批减仓")
        op.append("  ❌ 避免追高 (震荡市追涨容易被套)")
    elif "趋势" in regime:
        op.append("  ✅ 可加仓主线 (如科技/高端制造)")
        op.append("  ✅ 回调不破 MA20 可继续持有")
        op.append("  ✅ ETF 持续回流 + 放量突破 → 确认趋势延续")
        op.append("  ⚠️ 警惕 MA20 跌破后的趋势反转")
    else:
        op.append("  ✅ 以防守为主, 控制仓位")
        op.append("  ✅ 等待 MA60 企稳 + 量能萎缩 → 考虑抄底")
        op.append("  ❌ 不要接飞刀 (弱势市不言底)")

    op.append("\n📌 关键观察信号 (趋势确认需要同时满足):")
    op.append("  ① ETF 主力资金 连续 3日 净流入")
    op.append("  ② 成交量 放量突破 7000亿 (半日)")
    op.append("  ③ 上证指数 站稳 MA20 并放量")
    op.append("  ④ 龙头股 (算力/半导体) 率先突破新高")

    risk = ["⚠️ 风险控制 & 关键提醒\n"]
    risk.append("━" * 28)
    risk.append("\n🚨 止损条件 (触发任一即减仓/清仓):")
    risk.append("  🔴 ETF 主力资金 连续 5日 净流出")
    risk.append("  🔴 放量跌破 MA60 关键支撑")
    risk.append("  🔴 北向资金 连续 3日 大幅流出")
    risk.append("  🔴 跌停家数 > 50 且 涨停 < 30 (恐慌信号)")
    risk.append("\n📚 关键提醒:")
    risk.append("  • 短期 (1-5天) 预测难度大, 优先用 「ETF流向 + 成交量」 过滤噪音")
    risk.append("  • 中期 (1-3月) 结合技术结构 + 估值分位 定仓位")
    risk.append("  • 长期 (1年+) 锚定宏观政策 + 资金周期")
    risk.append("  • 本分析为市场规律总结, 不构成投资建议, 需结合自身风险承受力决策")

    return "\n".join(op), "\n".join(risk)
