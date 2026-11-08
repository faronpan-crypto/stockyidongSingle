"""🧊 情绪冰点修复扫描器 — 跌停翘板 / 冰期反转 / 情绪均值回归 v1.1

v1.1 新增: 第三列联动 K线 + 🌊一目均衡 + 📊附图指标
  双击左侧个股 → 右侧 Notebook 联动刷新

作者: stockyidong 团队
"""
import os, sys, re, json, time, threading, traceback, ssl, urllib.parse, urllib.request
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

try: import numpy as np
except ImportError: np = None
try: import pandas as pd
except ImportError: pd = None
try: import matplotlib; matplotlib.use("TkAgg")
except Exception: pass

# ═══════════════════════════════════════════════════════════
#  matplotlib 全局字体 (Mac PingFang SC 优先)
# ═══════════════════════════════════════════════════════════
matplotlib.rcParams["font.sans-serif"] = [
    "PingFang SC", "Heiti SC", "STHeiti", "Hiragino Sans GB",
    "Arial Unicode MS", "SimHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# ═══════════════════════════════════════════════════════════
#  配色 / 策略常量 (与原版 emotion_freeze.py 一致)
# ═══════════════════════════════════════════════════════════
_BG_DEEP     = "#121212"
_BG_PANEL    = "#1E1E1E"
_BG_CARD     = "#2A2A2A"
_BG_TOOLBAR  = "#1A1A1A"
_BG_RISK     = "#2D1F1F"
_FG_RED      = "#FF8A80"   # 涨
_FG_GREEN    = "#69F0AE"   # 跌
_FG_GOLD     = "#FFD54F"
_FG_BLUE     = "#90CAF9"
_FG_CYAN     = "#80DEEA"
_FG_PURPLE   = "#CE93D8"
_FG_ORANGE   = "#FFB74D"
_FG_TEXT     = "#E0E0E0"
_FG_DIM      = "#9E9E9E"
_FG_WHITE    = "#FFFFFF"

# U 选股池条件
U_MIN_CAP_EVAL = 20
U_MAX_CAP_EVAL = 150
U_MIN_DAILY_AMOUNT = 3.0
U_MIN_LIMIT_UP_COUNT = 2
U_MIN_HIGH_DRAWDOWN = 20
U_MAX_HIGH_DRAWDOWN = 45
U_MIN_LIST_DAYS = 60

# E 入场条件
E1_LIMIT_DOWN_MIN = 100
E1_UP_DOWN_RATIO_MAX = 1.0 / 3
E1_DOWN_COUNT_MIN = 4500
E2_MARGIN_CONSECUTIVE_DAYS = 5
E3_LIMIT_DOWN_PCT = -9.5
E3_DEEP_DROP_PCT = -9.0
E4_CATALYST_WINDOW_DAYS = 10
E5_ETF_VOLUME_100B = 100

# F 禁做过滤器
F1_VOLUME_SHRINK_PCT = 15
F1_TOP_HIGH_TURNOVER = 25


# ═══════════════════════════════════════════════════════════
#  K线数据获取 (独立顶级函数, 不依赖 mixin self)
# ═══════════════════════════════════════════════════════════

def _fetch_daily_kline_independent(code6, sina_code=None, days=200):
    """📈 独立版日K获取 — 不依赖 tab_jianlou, 优先新浪 / AkShare 兜底
    
    Returns DataFrame [date, open, high, low, close, volume] 或 None
    """
    import pandas as pd
    # 1) 新浪 scale=240 日K (已有)
    if sina_code is None:
        sina_code = f"sh{code6}" if str(code6).zfill(6).startswith(("6","5","9")) else f"sz{code6}"
    try:
        from ui.tab_jianlou import _fetch_kline_sina
        k = _fetch_kline_sina(sina_code, scale=240, datalen=days)
        if k and k.get("closes"):
            import pandas as pd
            df = pd.DataFrame({
                "date":   k.get("dates", []),
                "open":   k.get("opens", []),
                "high":   k.get("highs", []),
                "low":    k.get("lows", []),
                "close":  k.get("closes", []),
                "volume": k.get("volumes", []),
            })
            if len(df) >= 60:
                return df.tail(days).reset_index(drop=True)
    except Exception as e:
        print(f"[🧊K线新浪❌] {e}")

    # 2) AkShare 兜底
    try:
        import akshare as ak
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y%m%d')
        code6 = str(code6).zfill(6)
        df = ak.stock_zh_a_hist(symbol=code6, period="daily", adjust="qfq",
                                start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            col_map = {}
            for cn, en in [("日期", "date"), ("开盘", "open"), ("最高", "high"),
                           ("最低", "low"), ("收盘", "close"), ("成交量", "volume")]:
                if cn in df.columns: col_map[cn] = en
            df = df.rename(columns=col_map)
            df = df[["date","open","high","low","close","volume"]].reset_index(drop=True)
            if len(df) >= 60:
                return df
    except Exception as e:
        print(f"[🧊K线AkShare❌] {e}")
    return None


# ═══════════════════════════════════════════════════════════
#  一目均衡表 (Ichimoku) — 顶级函数版 (从 tab_stock_detail.py 独立)
# ═══════════════════════════════════════════════════════════

def _calc_ichimoku(highs, lows, closes):
    """📐 计算一目均衡 5 条线 + 云"""
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows,  dtype=float)
    c = np.asarray(closes,dtype=float)
    n = len(c)

    def _p_high(arr, p):
        out = np.full(n, np.nan)
        for i in range(n):
            s = max(0, i - p + 1)
            out[i] = np.max(arr[s:i+1])
        return out
    def _p_low(arr, p):
        out = np.full(n, np.nan)
        for i in range(n):
            s = max(0, i - p + 1)
            out[i] = np.min(arr[s:i+1])
        return out

    tenkan = (_p_high(h, 9) + _p_low(l, 9)) / 2.0
    kijun  = (_p_high(h, 26) + _p_low(l, 26)) / 2.0

    sen_a = (tenkan + kijun) / 2.0
    sen_a_x = np.full(n + 26, np.nan); sen_a_x[26:26+n] = sen_a

    sen_b = (_p_high(h, 52) + _p_low(l, 52)) / 2.0
    sen_b_x = np.full(n + 26, np.nan); sen_b_x[26:26+n] = sen_b

    chikou = np.full(n + 26, np.nan)
    shift = 26
    if n > shift:
        chikou[:n-shift] = c[shift:]

    return {"tenkan": tenkan, "kijun": kijun,
            "sen_a": sen_a_x, "sen_b": sen_b_x, "chikou": chikou}


def _plot_ichimoku(ax, df, n_show=120):
    """🌊 在已画好K线的 ax 上叠加一目均衡 (简化版)
    
    df: DataFrame with open/high/low/close/volume
    n_show: 显示最后 N 根 (带右侧 26 根预测区)
    """
    if df is None or len(df) < 60: return
    df = df.tail(n_show).reset_index(drop=True)
    x_arr = np.arange(len(df))
    highs = df["high"].values
    lows  = df["low"].values
    closes= df["close"].values

    ich = _calc_ichimoku(highs, lows, closes)
    n = len(df)
    ext_x = np.arange(n + 26)

    # 云 (Kumo)
    sen_a = ich["sen_a"]
    sen_b = ich["sen_b"]
    cloud_top = np.nanmax([sen_a, sen_b], axis=0)
    cloud_bot = np.nanmin([sen_a, sen_b], axis=0)
    ax.fill_between(ext_x, cloud_bot, cloud_top,
                    where=sen_a >= sen_b, color="#c62828", alpha=0.20)
    ax.fill_between(ext_x, cloud_bot, cloud_top,
                    where=sen_a <  sen_b, color="#2e7d32", alpha=0.20)

    # 先行带 A/B 虚线 (预测未来 26 根)
    ax.plot(ext_x, sen_a, color="#2196f3", lw=0.9, alpha=0.7, ls="--", label="先行带A")
    ax.plot(ext_x, sen_b, color="#ff9800", lw=0.9, alpha=0.7, ls="--", label="先行带B")

    # 转换线 Tenkan (粉) + 基准线 Kijun (绿)
    ax.plot(x_arr, ich["tenkan"], color="#e91e63", lw=1.1, label="转换线Tenkan")
    ax.plot(x_arr, ich["kijun"],  color="#4caf50", lw=1.1, label="基准线Kijun")

    # 迟行带 Chikou (蓝虚线, 画在过去)
    ax.plot(ext_x, ich["chikou"], color="#1976d2", lw=0.9, alpha=0.8, ls=":", label="迟行带Chikou")

    # 分隔线: n 位置 (实线K线区 vs 虚线预测区)
    ax.axvline(n - 0.5, color=_FG_DIM, lw=0.6, ls=":", alpha=0.5)
    ax.annotate("← K线区  |  预测26根 →", xy=(n - 0.5, ax.get_ylim()[1]),
                fontsize=8, color=_FG_DIM, ha="center", va="bottom")

    # 图例简化
    ax.legend(loc="upper left", fontsize=8, framealpha=0.6,
              labelcolor=_FG_TEXT, facecolor=_BG_PANEL, edgecolor=_FG_DIM)
    ax.set_facecolor(_BG_DEEP)
    for spine in ax.spines.values(): spine.set_color(_FG_DIM)
    ax.tick_params(colors=_FG_DIM, labelsize=8)


# ═══════════════════════════════════════════════════════════
#  蜡烛图绘制 (独立顶级函数)
# ═══════════════════════════════════════════════════════════

def _draw_candlestick(ax, df, n_show=120, ma_list=(5, 10, 20)):
    """📈 A股红涨绿跌蜡烛图 (简化版, 无依赖)"""
    if df is None or len(df) < 20: return
    df = df.tail(n_show).reset_index(drop=True)
    n = len(df)
    x = np.arange(n)
    opens, highs, lows, closes = [df[c].values for c in ["open","high","low","close"]]

    # A股红涨绿跌
    up_col = "#ff4d4f"   # 红
    dn_col = "#26a69a"   # 绿
    body_w = 0.7
    wick_w = 0.9

    for i in range(n):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        is_up = c >= o
        col = up_col if is_up else dn_col
        # 影线 (high-low)
        ax.plot([i, i], [l, h], color=col, lw=0.9, solid_capstyle="round")
        # 实体
        bot = min(o, c); top = max(o, c)
        body_h = max(top - bot, 0.001)
        rect = ax.bar(i, body_h, bottom=bot, width=body_w, color=col,
                      edgecolor=col, linewidth=0.5)

    # MA 均线
    for ma_p in ma_list:
        if n >= ma_p:
            ma_vals = pd.Series(closes).rolling(ma_p).mean().values
            ma_col = {5: "#ffeb3b", 10: "#ab47bc", 20: "#29b6f6", 60: "#ef5350"}.get(ma_p, "#cccccc")
            ax.plot(x, ma_vals, color=ma_col, lw=0.9, alpha=0.85, label=f"MA{ma_p}")

    ax.legend(loc="upper left", fontsize=8, framealpha=0.6,
              labelcolor=_FG_TEXT, facecolor=_BG_PANEL, edgecolor=_FG_DIM)
    ax.set_facecolor(_BG_DEEP)
    for spine in ax.spines.values(): spine.set_color(_FG_DIM)
    ax.tick_params(colors=_FG_DIM, labelsize=8)
    ax.set_xlim(-0.5, n - 0.5)

    # x 轴日期标签 (每 20 根显示一个)
    dates = df["date"].tolist() if "date" in df.columns else [str(i) for i in range(n)]
    step = max(1, n // 8)
    ticks = list(range(0, n, step)) + [n - 1]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(dates[i])[:10] if i < len(dates) else "" for i in ticks],
                       rotation=30, ha="right", fontsize=7, color=_FG_DIM)


def _draw_volume(ax_vol, df, n_show=120):
    """📊 成交量副图"""
    if df is None or len(df) < 20: return
    df = df.tail(n_show).reset_index(drop=True)
    n = len(df)
    x = np.arange(n)
    vols = df["volume"].values
    opens = df["open"].values
    closes = df["close"].values
    colors = ["#ff4d4f" if closes[i] >= opens[i] else "#26a69a" for i in range(n)]
    ax_vol.bar(x, vols, color=colors, alpha=0.7, width=0.7)
    ax_vol.set_facecolor(_BG_DEEP)
    for spine in ax_vol.spines.values(): spine.set_color(_FG_DIM)
    ax_vol.tick_params(colors=_FG_DIM, labelsize=7)
    ax_vol.set_xlim(-0.5, n - 0.5)
    ax_vol.set_ylabel("VOL", color=_FG_DIM, fontsize=8)


# ═══════════════════════════════════════════════════════════
#  (以下是原版扫描逻辑 — 数据层 + UI层)
# ═══════════════════════════════════════════════════════════

def _fetch_market_breadth():
    """📊 E1 大盘情绪冰点判定"""
    result = dict(limit_down=0, limit_up=0, down_count=0, up_count=0,
                  flat_count=0, ratio=None, total=0, freeze_flag=False,
                  source="empty", raw_df=None)
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is not None and len(df) > 1000:
            pct_col = None
            for c in ["涨跌幅", "涨跌幅(%)", "change_pct"]:
                if c in df.columns: pct_col = c; break
            if pct_col:
                s = df[pct_col].astype(float)
                result["limit_down"] = int((s <= E3_LIMIT_DOWN_PCT).sum())
                result["limit_up"]   = int((s >= 9.5).sum())
                result["down_count"] = int((s < 0).sum())
                result["up_count"]   = int((s > 0).sum())
                result["flat_count"] = int((s == 0).sum())
                result["total"]      = len(df)
                result["ratio"]      = round(result["limit_up"] / max(result["limit_down"], 1), 2)
                result["source"]     = "东财全市场"
                result["raw_df"]     = df
                flags = [result["limit_down"] >= E1_LIMIT_DOWN_MIN,
                         result["limit_up"] / max(result["limit_down"], 1) <= E1_UP_DOWN_RATIO_MAX,
                         result["down_count"] >= E1_DOWN_COUNT_MIN]
                result["freeze_flag"] = sum(flags) >= 2
                return result
    except Exception as e:
        print(f"[🧊breadth❌] AkShare东财连不上: {e}")

    try:
        from ui.tab_jianlou import _load_watchlist, _fetch_hq_batch
        pool = _load_watchlist()
        sina_codes = [sina for _, sina, _ in pool]
        hq = _fetch_hq_batch(sina_codes)
        if hq:
            downs = ups = flats = lim_dn = lim_up = 0
            for v in hq.values():
                c = v.get("chg", 0)
                if c <= E3_LIMIT_DOWN_PCT: lim_dn += 1
                if c >= 9.5: lim_up += 1
                if c < 0: downs += 1
                elif c > 0: ups += 1
                else: flats += 1
            result["limit_down"] = lim_dn; result["limit_up"] = lim_up
            result["down_count"] = downs; result["up_count"] = ups
            result["flat_count"] = flats; result["total"] = len(hq)
            result["ratio"] = round(lim_up/max(lim_dn,1),2) if lim_dn else None
            result["source"] = f"自选池({len(hq)}只)"
            flags = [lim_dn>=5, lim_up/max(lim_dn,1)<=3.0 if lim_dn else False, downs>=40]
            result["freeze_flag"] = sum(flags) >= 2
    except Exception as e:
        print(f"[🧊breadth❌] 自选池挂了: {e}")
    return result


def _fetch_margin_trend(days=10):
    """📈 E2 两融余额趋势"""
    result = dict(consecutive_down=0, trend="unknown", recent_values=[],
                  freeze_flag=False, source="empty")
    try:
        import akshare as ak
        df_sh = ak.macro_china_market_margin_sh()
        df_sz = ak.macro_china_market_margin_sz()
        if df_sh is not None and df_sz is not None:
            sh_col = [c for c in df_sh.columns if '余额' in str(c) or '融资' in str(c)]
            sz_col = [c for c in df_sz.columns if '余额' in str(c) or '融资' in str(c)]
            if sh_col and sz_col:
                sh_v = df_sh[sh_col[0]].astype(float).tolist()[-days:]
                sz_v = df_sz[sz_col[0]].astype(float).tolist()[-days:]
                n = min(len(sh_v), len(sz_v))
                total = [sh_v[-n-i] + sz_v[-n-i] for i in range(n)]
                consec = 0
                for i in range(1, len(total)):
                    if total[i] < total[i-1]: consec += 1
                    else: break
                result["consecutive_down"] = consec
                result["recent_values"] = [round(v, 1) for v in reversed(total)]
                result["freeze_flag"] = consec >= E2_MARGIN_CONSECUTIVE_DAYS
                result["source"] = "沪深两融"
    except Exception as e:
        print(f"[🧊margin❌] {e}")
    return result


def _scan_universe(df_spot=None, watchlist_pool=None):
    """🎯 U1-U6 选股池过滤"""
    import pandas as pd
    filters = {f"U{i}": 0 for i in range(1, 7)}
    if df_spot is not None and len(df_spot) > 1000:
        try:
            df = df_spot.copy()
            name_col    = next((c for c in df.columns if '名称' in c), None)
            code_col    = next((c for c in df.columns if c == '代码' or '代码' in c), None)
            cap_col     = next((c for c in df.columns if '流通市值' in c or ('市值' in c and '流通' not in c)), None)
            amount_col  = next((c for c in df.columns if '成交额' in c), None)
            if name_col and code_col:
                df = df[~df[name_col].str.contains(r'ST|退', na=False)]
                filters["U1"] = len(df)
                if cap_col:
                    cap_yi = df[cap_col].astype(float) / 1e8
                    mask = (cap_yi >= U_MIN_CAP_EVAL) & (cap_yi <= U_MAX_CAP_EVAL)
                    df = df[mask]; filters["U2"] = len(df)
                if amount_col:
                    amt = df[amount_col].astype(float)
                    amt_yi = amt / 1e8 if amt.max() > 1e6 else amt
                    df = df[amt_yi >= U_MIN_DAILY_AMOUNT]; filters["U5"] = len(df)
                df["_tag"] = ""
                if watchlist_pool:
                    wc = {c6: tag for c6, _, tag in watchlist_pool}
                    df["_tag"] = df[code_col].astype(str).map(wc).fillna("")
                return df, filters
        except Exception as e:
            print(f"[🧊universe❌] AkShare过滤炸了: {e}")

    if watchlist_pool:
        try:
            from ui.tab_jianlou import _fetch_hq_batch
            sina_codes = [sina for _, sina, _ in watchlist_pool]
            hq = _fetch_hq_batch(sina_codes)
            rows = []
            for c6, sina, tag in watchlist_pool:
                h = hq.get(sina, {})
                rows.append({"代码": c6, "名称": h.get("name",""), "最新价": h.get("price",0),
                             "涨跌幅": h.get("chg",0), "_tag": tag, "_sina": sina, "_source": "自选池"})
            filters["U1"] = len(rows)
            import pandas as pd
            return pd.DataFrame(rows), filters
        except Exception as e:
            print(f"[🧊universe❌] 自选池炸了: {e}")
    import pandas as pd
    return pd.DataFrame(), filters


# ═══════════════════════════════════════════════════════════
#  UI 主体 (show_emotion_freeze) — 右侧 Notebook + 双击联动
# ═══════════════════════════════════════════════════════════

def show_emotion_freeze(root=None, app=None):
    """🧊 情绪冰点修复扫描器主函数 v1.1 (K线 + 一目均衡 联动)"""
    import pandas as pd

    dlg = tk.Toplevel(root)
    dlg.title("🧊 情绪冰点修复 — 跌停翘板 / 冰期反转 / 情绪均值回归")
    dlg.geometry("1580x920")   # 加了第三列, 更宽
    dlg.configure(bg=_BG_DEEP)
    dlg.transient(root)
    dlg.minsize(1280, 780)

    # ── 顶栏 ──
    top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=48); top.pack(fill=tk.X)
    top.pack_propagate(False)
    tk.Label(top, text="🧊 情绪冰点修复扫描器", bg=_BG_TOOLBAR, fg=_FG_CYAN,
             font=("TkDefaultFont", 16, "bold")).pack(side=tk.LEFT, padx=12, pady=8)
    tk.Label(top, text="  跌停翘板 · 冰期反转 · 情绪均值回归",
             bg=_BG_TOOLBAR, fg=_FG_DIM, font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=4)
    status = tk.Label(top, text="⏳ 待扫描", bg=_BG_TOOLBAR, fg=_FG_DIM,
                      font=("TkDefaultFont", 12))
    status.pack(side=tk.RIGHT, padx=12)
    scan_btn = tk.Button(top, text="🔄 一键扫描", command=lambda: None,
                         bg=_BG_PANEL, fg=_FG_GOLD, activebackground=_BG_CARD,
                         activeforeground=_FG_GOLD,
                         font=("TkDefaultFont", 13, "bold"),
                         relief=tk.FLAT, padx=14, pady=4, cursor="hand2")
    scan_btn.pack(side=tk.LEFT, padx=10, pady=8)
    tk.Button(top, text="📋 策略文档", command=lambda: _show_strategy_doc(dlg),
              bg=_BG_PANEL, fg=_FG_BLUE, relief=tk.FLAT, padx=8, pady=3).pack(side=tk.LEFT, padx=4)
    tk.Button(top, text="🤖 多AI验证", command=lambda: _show_ai_prompt(dlg),
              bg=_BG_PANEL, fg=_FG_PURPLE, relief=tk.FLAT, padx=8, pady=3).pack(side=tk.LEFT, padx=4)

    # ── 情绪温度计仪表盘 ──
    gauge = tk.Frame(dlg, bg=_BG_PANEL, height=60); gauge.pack(fill=tk.X)
    gauge.pack_propagate(False)
    gauge_labels = {}
    for i, (key, label) in enumerate([
        ("e1", "💧 E1 大盘冰点"), ("limit_down", "跌停家数"), ("limit_up", "涨停家数"),
        ("down_cnt", "下跌家数"), ("ratio", "涨停/跌停"),
        ("e2", "📉 E2 两融趋势"), ("margin_cd", "连降天数"), ("f1", "⚠️ F1 禁做"),
    ]):
        cell = tk.Frame(gauge, bg=_BG_PANEL)
        cell.pack(side=tk.LEFT, padx=6, pady=6, expand=True, fill=tk.X)
        tk.Label(cell, text=label, bg=_BG_PANEL, fg=_FG_DIM,
                 font=("TkDefaultFont", 10)).pack(anchor="w")
        lbl = tk.Label(cell, text="—", bg=_BG_PANEL, fg=_FG_DIM,
                       font=("TkDefaultFont", 13, "bold"))
        lbl.pack(anchor="w")
        gauge_labels[key] = lbl

    # ── 主容器: 左列表 + 右(K线+详情) ──
    main = tk.Frame(dlg, bg=_BG_DEEP); main.pack(fill=tk.BOTH, expand=True)

    # ═══ 左侧列表 Notebook ═══
    left = tk.Frame(main, bg=_BG_DEEP, width=500); left.pack(side=tk.LEFT, fill=tk.Y, padx=(6,3), pady=6)
    left.pack_propagate(False)

    # ═══ 右侧: 顶部详情概览 + 底部 K线 Notebook ═══
    right = tk.Frame(main, bg=_BG_DEEP); right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3,6), pady=6)

    # 顶部详情概览 (精简版三栏, 高度固定 110px)
    right_header = tk.Frame(right, bg=_BG_CARD, height=110)
    right_header.pack(fill=tk.X, pady=(0, 4))
    right_header.pack_propagate(False)
    rh_title = tk.Label(right_header, text="📖 点击/双击左侧个股联动K线",
                        bg=_BG_CARD, fg=_FG_DIM, font=("TkDefaultFont", 11))
    rh_title.pack(anchor="w", padx=10, pady=(6,2))
    rh_text = tk.Label(right_header, text="—",
                       bg=_BG_CARD, fg=_FG_TEXT, font=("TkDefaultFont", 10),
                       justify="left", anchor="nw")
    rh_text.pack(anchor="w", padx=10, pady=(0,6), fill=tk.BOTH, expand=True)

    # 底部 Notebook: 📈日K线 + 🌊一目均衡 + 📊附图指标
    right_nb = ttk.Notebook(right)
    right_nb.pack(fill=tk.BOTH, expand=True)

    tab_kline  = tk.Frame(right_nb, bg=_BG_DEEP);  right_nb.add(tab_kline,  text="📈 日K线")
    tab_ichi   = tk.Frame(right_nb, bg=_BG_DEEP);  right_nb.add(tab_ichi,   text="🌊 一目均衡")
    tab_ind    = tk.Frame(right_nb, bg=_BG_DEEP);  right_nb.add(tab_ind,    text="📊 附图指标")

    # matplotlib Figure 容器 (每个 tab 各自一张 Figure)
    fig_kline = Figure(figsize=(10, 5.5), dpi=100, facecolor=_BG_DEEP)
    fig_ichi  = Figure(figsize=(10, 5.5), dpi=100, facecolor=_BG_DEEP)
    fig_ind   = Figure(figsize=(10, 5.5), dpi=100, facecolor=_BG_DEEP)

    canvas_kline = FigureCanvasTkAgg(fig_kline, master=tab_kline); canvas_kline.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    canvas_ichi  = FigureCanvasTkAgg(fig_ichi,  master=tab_ichi);   canvas_ichi.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    canvas_ind   = FigureCanvasTkAgg(fig_ind,   master=tab_ind);    canvas_ind.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # 加 matplotlib 工具栏 (可选)
    try:
        tb_k = NavigationToolbar2Tk(canvas_kline, tab_kline, pack_toolbar=False); tb_k.pack(fill=tk.X)
        tb_i = NavigationToolbar2Tk(canvas_ichi,  tab_ichi,   pack_toolbar=False); tb_i.pack(fill=tk.X)
        tb_n = NavigationToolbar2Tk(canvas_ind,   tab_ind,    pack_toolbar=False); tb_n.pack(fill=tk.X)
    except Exception:
        pass

    # ── 左侧 Notebook 样式 ──
    style = ttk.Style()
    try:
        style.theme_use("clam")
        style.configure("Fz.TNotebook", background=_BG_DEEP, borderwidth=0)
        style.configure("Fz.TNotebook.Tab", background=_BG_PANEL, foreground=_FG_TEXT,
                        padding=(12, 5), font=("TkDefaultFont", 11))
        style.map("Fz.TNotebook.Tab", background=[("selected", _BG_CARD)],
                  foreground=[("selected", _FG_GOLD)])
    except Exception: pass

    nb = ttk.Notebook(left, style="Fz.TNotebook")
    nb.pack(fill=tk.BOTH, expand=True)
    tab_freeze    = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_freeze,    text="🧊 冰点触发")
    tab_candidate = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_candidate, text="🏆 候选池")
    tab_risk      = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_risk,      text="⚠️ 禁做信号")

    def _make_scrollable(parent):
        cv = tk.Canvas(parent, bg=_BG_DEEP, highlightthickness=0)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=cv.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        cv.configure(yscrollcommand=sb.set)
        inner = tk.Frame(cv, bg=_BG_DEEP)
        cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Enter>", lambda e: cv.bind_all("<MouseWheel>",
                  lambda ev: cv.yview_scroll(-1 if ev.delta > 0 else 1, "units")))
        cv.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))
        return cv, inner

    _, inner_freeze    = _make_scrollable(tab_freeze)
    _, inner_candidate = _make_scrollable(tab_candidate)
    _, inner_risk      = _make_scrollable(tab_risk)

    # ═══════════════════════════════════════════════════════
    #  核心: 联动渲染函数 — 点击/双击个股 → 右侧刷新
    # ═══════════════════════════════════════════════════════
    _current_kdf_cache = {}  # {sina_code: DataFrame} 缓存, 避免重复拉

    def _render_right(row_or_dict):
        """📊 联动刷新右侧: 详情概览 + K线 + 一目均衡 + 附图"""
        code  = str(row_or_dict.get("代码", row_or_dict.get("code", ""))).zfill(6)
        name  = row_or_dict.get("名称", row_or_dict.get("name", ""))
        pct   = row_or_dict.get("涨跌幅", row_or_dict.get("chg", 0))
        price = row_or_dict.get("最新价", row_or_dict.get("price", 0))
        tag   = row_or_dict.get("_tag", "")
        sina  = row_or_dict.get("_sina") or (f"sh{code}" if code.startswith(("6","5","9")) else f"sz{code}")
        e_flags = row_or_dict.get("e_flags", [])
        e_score = row_or_dict.get("e_score", 0)

        # 1) 顶部详情概览
        pct_str = f"{pct:.2f}%" if isinstance(pct,(int,float)) else str(pct)
        pct_fg = _FG_RED if isinstance(pct,(int,float)) and pct <= E3_LIMIT_DOWN_PCT else _FG_ORANGE if isinstance(pct,(int,float)) and pct <= E3_DEEP_DROP_PCT else _FG_TEXT
        lines = [
            f"🎯 {code}  {name}  [{tag or '自选外'}]",
            f"📉 {pct_str}   💰 {price:.2f}" if isinstance(price,(int,float)) else f"📉 {pct_str}",
            f"{' | '.join(e_flags) if e_flags else '—'}",
            f"🧊 策略评分: {e_score:.0f}   U2: 20-150亿   U5: ≥3亿成交额",
            "",
            "双击左侧个股 → 自动切到 📈日K线 / 🌊一目均衡 / 📊附图指标",
        ]
        rh_text.config(text="\n".join(lines))
        rh_title.config(text=f"📖 {code}  {name}")

        # 2) 清旧图
        for fig in (fig_kline, fig_ichi, fig_ind):
            fig.clear()

        # 3) 拉 K线 (带缓存)
        kdf = _current_kdf_cache.get(sina)
        if kdf is None or len(kdf) < 60:
            code6 = sina[2:] if len(sina)==8 else code
            dlg.after(0, lambda: status.config(text=f"⏳ 拉取 {name} 日K..."))
            try:
                kdf = _fetch_daily_kline_independent(code6, sina_code=sina, days=200)
                if kdf is not None:
                    _current_kdf_cache[sina] = kdf
                    dlg.after(0, lambda: status.config(
                        text=f"✅ {name} 日K {len(kdf)}根 | 评分 {e_score:.0f}", fg=_FG_GOLD))
                else:
                    dlg.after(0, lambda: status.config(text=f"⚠️ {name} 日K拉不到", fg=_FG_ORANGE))
            except Exception as e:
                dlg.after(0, lambda: status.config(text=f"❌ K线拉取炸了: {e}", fg=_FG_RED))

        if kdf is not None and len(kdf) >= 20:
            # ── 📈 Tab1: 日K线 + MA ──
            ax_k = fig_kline.add_subplot(111)
            _draw_candlestick(ax_k, kdf, n_show=120, ma_list=(5,10,20,60))
            ax_k.set_title(f"{name} ({code}) 📈 日K线", color=_FG_CYAN, fontsize=12, fontweight="bold")
            fig_kline.tight_layout(); canvas_kline.draw_idle()

            # ── 🌊 Tab2: 一目均衡 ──
            ax_i = fig_ichi.add_subplot(111)
            # 先画蜡烛图 (浅灰)
            n_df = kdf.tail(120).reset_index(drop=True)
            _draw_candlestick(ax_i, kdf, n_show=120, ma_list=())  # MA空, 只蜡烛
            # 再叠加一目均衡
            _plot_ichimoku(ax_i, kdf, n_show=120)
            ax_i.set_title(f"{name} ({code}) 🌊 一目均衡表 (Ichimoku)", color=_FG_CYAN, fontsize=12, fontweight="bold")
            fig_ichi.tight_layout(); canvas_ichi.draw_idle()

            # ── 📊 Tab3: 附图指标 (成交量 + MACD 简化) ──
            ax_v = fig_ind.add_subplot(211)
            _draw_candlestick(ax_v, kdf, n_show=120, ma_list=(5,10,20))
            ax_v.set_title(f"{name} ({code}) 📊 日K线", color=_FG_CYAN, fontsize=11, fontweight="bold")

            ax_vol = fig_ind.add_subplot(212, sharex=ax_v)
            _draw_volume(ax_vol, kdf, n_show=120)
            fig_ind.tight_layout(); canvas_ind.draw_idle()
        else:
            # 拉不到 K线 → 显示提示
            for fig, label in [(fig_kline, "📈日K线"), (fig_ichi, "🌊一目均衡"), (fig_ind, "📊附图")]:
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, f"⚠️ {label} K线数据不足\n请检查网络或稍后重试",
                        transform=ax.transAxes, ha="center", va="center",
                        fontsize=14, color=_FG_DIM)
                ax.set_facecolor(_BG_DEEP); ax.axis("off")
                fig.tight_layout()
            canvas_kline.draw_idle(); canvas_ichi.draw_idle(); canvas_ind.draw_idle()

    def _on_card_click(row):
        """单击 → 刷新右侧但不切 tab"""
        _render_right(row)

    def _on_card_double(row):
        """双击 → 刷新右侧 + 切到 📈日K线 tab"""
        _render_right(row)
        try: right_nb.select(0)  # 切到第一个 tab (📈日K线)
        except Exception: pass

    # ═══════════════════════════════════════════════════════
    #  扫描后台 + 仪表盘更新
    # ═══════════════════════════════════════════════════════
    def _update_gauge_e1(b):
        if b["freeze_flag"]: gauge_labels["e1"].config(text="❄️ 冰点触发", fg=_FG_RED)
        elif b["limit_down"] >= E1_LIMIT_DOWN_MIN // 2: gauge_labels["e1"].config(text="⚠️ 接近冰点", fg=_FG_ORANGE)
        else: gauge_labels["e1"].config(text="✅ 正常", fg=_FG_GREEN)
        gauge_labels["limit_down"].config(text=f"{b['limit_down']}只", fg=_FG_RED if b["limit_down"]>=E1_LIMIT_DOWN_MIN else _FG_DIM)
        gauge_labels["limit_up"].config(text=f"{b['limit_up']}只")
        gauge_labels["down_cnt"].config(text=f"{b['down_count']}只/{b['total']}只")
        r = b.get("ratio"); gauge_labels["ratio"].config(text=f"{r:.2f}" if r is not None else "—")

    def _update_gauge_e2(m):
        if m["freeze_flag"]: gauge_labels["e2"].config(text="📉 杠杆出清", fg=_FG_RED)
        elif m["consecutive_down"] >= 3: gauge_labels["e2"].config(text="⚠️ 连降中", fg=_FG_ORANGE)
        else: gauge_labels["e2"].config(text="✅ 平稳", fg=_FG_GREEN)
        gauge_labels["margin_cd"].config(text=f"{m['consecutive_down']}天连降")
        gauge_labels["f1"].config(text="🔴 退潮" if m["consecutive_down"]>=7 else "🟢 安全",
                                  fg=_FG_RED if m["consecutive_down"]>=7 else _FG_GREEN)

    def _run_scan():
        scan_btn.config(state=tk.DISABLED, text="⏳ 扫描中...")
        def _bg():
            try:
                breadth = _fetch_market_breadth()
                dlg.after(0, lambda: _update_gauge_e1(breadth))
                margin = _fetch_margin_trend()
                dlg.after(0, lambda: _update_gauge_e2(margin))
                from ui.tab_jianlou import _load_watchlist
                watchlist = _load_watchlist()
                universe, u_filters = _scan_universe(df_spot=breadth.get("raw_df"), watchlist_pool=watchlist)
                dlg.after(0, lambda: _populate_candidates(universe, u_filters))
                freeze_list, risk_signals = _check_entry_exit(universe, breadth, margin)
                dlg.after(0, lambda: _populate_freeze(freeze_list))
                dlg.after(0, lambda: _populate_risk(risk_signals))
                dlg.after(0, lambda: status.config(
                    text=f"✅ 扫描完成 | 冰点 {len(freeze_list)}只 | 候选 {len(universe)}只",
                    fg=_FG_GOLD))
            except Exception as e:
                traceback.print_exc()
                dlg.after(0, lambda: status.config(text=f"❌ 扫描炸了: {e}", fg=_FG_RED))
            finally:
                dlg.after(0, lambda: scan_btn.config(state=tk.NORMAL, text="🔄 一键扫描"))
        threading.Thread(target=_bg, daemon=True).start()
    scan_btn.config(command=_run_scan)

    # ═══════════════════════════════════════════════════════
    #  三个填充函数 (复用原版, 改点击→联动右侧)
    # ═══════════════════════════════════════════════════════
    def _populate_candidates(universe, u_filters):
        for w in inner_candidate.winfo_children(): w.destroy()
        stats = tk.Frame(inner_candidate, bg=_BG_CARD, padx=8, pady=6)
        stats.pack(fill=tk.X, padx=4, pady=(4,2))
        tk.Label(stats, text="🎯 U1-U6 选股池", bg=_BG_CARD, fg=_FG_GOLD,
                 font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        tk.Label(stats, text="  →  ".join(f"U{i}={v}" for i,v in u_filters.items()),
                 bg=_BG_CARD, fg=_FG_DIM, font=("TkDefaultFont", 10)).pack(anchor="w")
        if universe is None or len(universe) == 0:
            tk.Label(inner_candidate, text="⏳ 还没有扫描数据, 或当前市场无符合条件个股\n\n"
                     "情绪冰点反包策略只在恐慌性跌停潮后才会触发\n平常日子候选池可能为空 — 这是正常的!",
                     bg=_BG_DEEP, fg=_FG_DIM, font=("TkDefaultFont", 11), justify="center").pack(pady=40)
            return

        for _, row in universe.iterrows():
            code = str(row.get("代码", row.get("code", ""))); name = row.get("名称", row.get("name",""))
            pct  = row.get("涨跌幅", row.get("chg", 0))
            price= row.get("最新价", row.get("price", 0))
            tag  = row.get("_tag", "")
            pct = float(pct) if isinstance(pct,(int,float)) else 0
            chg_color = _FG_RED if pct <= E3_LIMIT_DOWN_PCT else _FG_ORANGE if pct <= E3_DEEP_DROP_PCT else _FG_TEXT

            card = tk.Frame(inner_candidate, bg=_BG_CARD, padx=8, pady=6, cursor="hand2")
            card.pack(fill=tk.X, padx=4, pady=2)
            top_r = tk.Frame(card, bg=_BG_CARD); top_r.pack(fill=tk.X)
            tk.Label(top_r, text=f"{code}  {name}", bg=_BG_CARD, fg=_FG_WHITE,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
            if tag: tk.Label(top_r, text=f"[{tag}]", bg=_BG_CARD, fg=_FG_CYAN,
                             font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=4)
            tk.Label(top_r, text=f"{pct:.2f}%", bg=_BG_CARD, fg=chg_color,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.RIGHT)
            tk.Label(top_r, text=f"💰 {price:.2f}" if isinstance(price,(int,float)) else "",
                     bg=_BG_CARD, fg=_FG_DIM, font=("TkDefaultFont", 11)).pack(side=tk.RIGHT, padx=8)

            for w in [card, top_r] + list(top_r.winfo_children()):
                w.bind("<Button-1>",    lambda e, r=row.to_dict() if hasattr(row,'to_dict') else row: _on_card_click(r))
                w.bind("<Double-Button-1>", lambda e, r=row.to_dict() if hasattr(row,'to_dict') else row: _on_card_double(r))

    def _populate_freeze(freeze_list):
        for w in inner_freeze.winfo_children(): w.destroy()
        header = tk.Frame(inner_freeze, bg=_BG_RISK, padx=10, pady=8)
        header.pack(fill=tk.X, padx=4, pady=(4,6))
        tk.Label(header, text="🧊 冰点触发池 — E1+E2+E3 同时命中 (候选跌停翘板)",
                 bg=_BG_RISK, fg=_FG_GOLD, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        tk.Label(header, text="⚠️ 左侧接刀, 必须等 E5 承接信号确认再进! 严格执行 X3 止损!",
                 bg=_BG_RISK, fg=_FG_ORANGE, font=("TkDefaultFont", 10)).pack(anchor="w")
        if not freeze_list:
            tk.Label(inner_freeze, text="⏳ 暂无个股同时满足 E1+E2+E3\n\n"
                     "E1大盘冰点 + E2两融连降 + E3个股跌停/深跌\n三条件同时命中才开仓 — 宁缺毋滥!",
                     bg=_BG_DEEP, fg=_FG_DIM, font=("TkDefaultFont", 11), justify="center").pack(pady=40)
            return
        for item in freeze_list:
            code = str(item.get("代码", "?")); name = item.get("名称", "")
            pct  = float(item.get("涨跌幅", item.get("chg", 0)))
            score= item.get("e_score", 0); flags = item.get("e_flags", [])

            card = tk.Frame(inner_freeze, bg=_BG_RISK, padx=10, pady=8, cursor="hand2")
            card.pack(fill=tk.X, padx=4, pady=3)
            r1 = tk.Frame(card, bg=_BG_RISK); r1.pack(fill=tk.X)
            tk.Label(r1, text=f"🎯 {code}  {name}", bg=_BG_RISK, fg=_FG_WHITE,
                     font=("TkDefaultFont", 13, "bold")).pack(side=tk.LEFT)
            tk.Label(r1, text=f"E综合分 {score:.0f}", bg=_BG_RISK, fg=_FG_GOLD,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.RIGHT)
            r2 = tk.Frame(card, bg=_BG_RISK); r2.pack(fill=tk.X, pady=(4,0))
            tk.Label(r2, text=f"📉 {pct:.2f}%", bg=_BG_RISK, fg=_FG_RED,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
            tk.Label(r2, text=" | ".join(flags), bg=_BG_RISK, fg=_FG_CYAN,
                     font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=10)

            for w in [card, r1, r2] + list(r1.winfo_children()) + list(r2.winfo_children()):
                w.bind("<Button-1>", lambda e, it=item: _on_card_click(it))
                w.bind("<Double-Button-1>", lambda e, it=item: _on_card_double(it))

    def _populate_risk(risk_signals):
        for w in inner_risk.winfo_children(): w.destroy()
        header = tk.Frame(inner_risk, bg=_BG_CARD, padx=10, pady=8)
        header.pack(fill=tk.X, padx=4, pady=(4,6))
        tk.Label(header, text="⚠️ F1 大盘退潮 / 禁做过滤器", bg=_BG_CARD,
                 fg=_FG_ORANGE, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        if not risk_signals:
            tk.Label(inner_risk, text="✅ 当前无退潮信号 — 可以正常扫描\n\n"
                     "F1 禁做条件: 空间板断板+梯队断层 / 昨日涨停溢价<0 / "
                     "高位巨量滞涨 / 成交萎缩>15% / ETF持续净流出 / 外围风险事件",
                     bg=_BG_DEEP, fg=_FG_GREEN, font=("TkDefaultFont", 11), justify="left").pack(pady=20, padx=12)
            return
        for sig in risk_signals:
            level = sig.get("level","warn")
            bg = _BG_RISK if level=="danger" else _BG_CARD
            fg = _FG_RED if level=="danger" else _FG_ORANGE
            icon = "🔴" if level=="danger" else "🟡"
            card = tk.Frame(inner_risk, bg=bg, padx=10, pady=8)
            card.pack(fill=tk.X, padx=4, pady=3)
            tk.Label(card, text=f"{icon} {sig.get('title','信号')}", bg=bg, fg=fg,
                     font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
            tk.Label(card, text=sig.get("detail",""), bg=bg, fg=_FG_DIM,
                     font=("TkDefaultFont", 10), wraplength=580, justify="left").pack(anchor="w", pady=(2,0))

    def _check_entry_exit(universe, breadth, margin):
        freeze_list, risk_signals = [], []
        if universe is None or len(universe) == 0: return freeze_list, risk_signals
        if margin.get("consecutive_down", 0) >= 7:
            risk_signals.append(dict(level="danger", title="🔴 F1-2: 杠杆退潮 — 两融连续下降≥7天",
                detail=f"杠杆资金持续撤退 → 反弹高度受限, 冰点反包胜率显著下降\n历史回测: 两融连降7天后胜率从65%→32%"))
        if breadth.get("freeze_flag") and breadth.get("limit_down",0) < 50:
            risk_signals.append(dict(level="warn", title="🟡 F1: 弱冰点 — 跌停家数偏少",
                detail=f"跌停仅{breadth.get('limit_down')}只, 但下跌{breadth.get('down_count')}只\n阴跌而非恐慌砸盘, 策略胜率较低"))

        e1_hit = breadth.get("freeze_flag", False)
        e2_hit = margin.get("consecutive_down", 0) >= 3
        for _, row in universe.iterrows() if hasattr(universe,'iterrows') else []:
            pct = row.get("涨跌幅", row.get("chg", 0))
            if not isinstance(pct,(int,float)): continue
            e_flags, e_score = [], 0
            if e1_hit: e_flags.append("E1✅大盘冰点"); e_score += 25
            if e2_hit: e_flags.append("E2✅两融连降"); e_score += 20
            elif margin.get("consecutive_down",0) >= 1: e_score += 5
            if pct <= E3_LIMIT_DOWN_PCT: e_flags.append("E3✅跌停"); e_score += 35
            elif pct <= E3_DEEP_DROP_PCT: e_flags.append("E3⚠️深跌"); e_score += 25
            tag = row.get("_tag","")
            if tag in ("龙头","持仓"): e_flags.append(f"E5💡{tag}"); e_score += 10
            e3_hit = pct <= E3_DEEP_DROP_PCT
            if (e1_hit and e2_hit and e3_hit) or (e3_hit and e_score >= 40):
                item = row.to_dict() if hasattr(row, "to_dict") else dict(row)
                item["e_flags"], item["e_score"] = e_flags, e_score
                freeze_list.append(item)
        freeze_list.sort(key=lambda x: x.get("e_score",0), reverse=True)
        return freeze_list, risk_signals

    # 返回 dlg 供外部关闭
    return dlg


# ═══════════════════════════════════════════════════════════
#  策略文档 / AI Prompt 弹窗 (精简版, 完整版已在原版)
# ═══════════════════════════════════════════════════════════

_STRATEGY_DOC = """🧊 情绪冰点反包策略 v1.1 (K线 + 一目均衡联动版)

扫描入口: 🧊冰点修复按钮 (Row2)
右侧详情: 单击 = 刷新详情概览 + K线 + 一目均衡
          双击 = 刷新 + 切到 📈日K线 tab

═══════════════════════════════════════════════════════
一、策略定义
═══════════════════════════════════════════════════════
在市场情绪极端冰点日(恐慌性跌停潮), 买入有硬催化的前期
强势题材股的跌停/深跌错杀盘, 博情绪修复出现反包(涨停),
在涨停或次日冲高时兑现。本质: 赚"恐慌错杀→情绪修复"的钱。

═══════════════════════════════════════════════════════
二、E1-E3 量化入场条件 (缺一不做)
═══════════════════════════════════════════════════════
E1 大盘冰点: 跌停≥100只 或 涨停:跌停≤1:3 或 下跌≥4500只 (3选2)
E2 杠杆出清: 两融余额连续≥5天下降
E3 个股恐慌: 跌停(-9.5%以下) 或 深跌(-9%), 非自身利空

═══════════════════════════════════════════════════════
三、F1 禁做过滤器 (任意两条即空仓)
═══════════════════════════════════════════════════════
• 两融连降≥7天 (杠杆退潮)
• 弱冰点 (跌停家数偏少, 阴跌而非恐慌)
• 空间板断板+梯队断层
• 高位龙头放巨量滞涨
• 外围风险 (美债/油价/地缘/AI财报)

═══════════════════════════════════════════════════════
四、⚠️ 风险提示
═══════════════════════════════════════════════════════
• 这是高胜率环境下的幸存者样本 (2026年7-8月两次冰点
  都有国家队ETF托底, 无承接环境下胜率暴降)
• 跌停板买入 = 左侧接飞刀 — 严格执行 E1-E6 + X3 止损
• 缺条件宁可不买!
"""

_AI_PROMPT = """你是A股短线情绪策略风控官。请审查"情绪冰点反包"策略:

1) 该策略的主要失效环境是什么? 列出至少3种。
2) 入场 E1-E6 中哪一条最脆弱?
3) 模拟2026年7-8月在云南锗业/贤丰控股上的买卖推演。
4) 你认为需要增加哪条风控?

═══════════════════════════════════════════════════════
策略: 冰点日(E1跌停≥100/涨停:跌停≤1:3/下跌≥4500 3选2)
      + E2两融连降≥5天 + E3个股跌停/深跌(-9%以上)
      → 博情绪修复反包涨停, 涨停/次日冲高兑现

═══════════════════════════════════════════════════════
"""

def _show_strategy_doc(parent):
    dlg = tk.Toplevel(parent); dlg.title("📋 策略文档")
    dlg.geometry("720x620"); dlg.configure(bg=_BG_DEEP)
    st = tk.Text(dlg, wrap="word", bg=_BG_DEEP, fg=_FG_TEXT, font=("Menlo", 11),
                 relief=tk.FLAT, padx=14, pady=12, state=tk.DISABLED)
    st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    st.config(state=tk.NORMAL); st.insert("1.0", _STRATEGY_DOC); st.config(state=tk.DISABLED)

def _show_ai_prompt(parent):
    dlg = tk.Toplevel(parent); dlg.title("🤖 多AI交叉验证")
    dlg.geometry("720x620"); dlg.configure(bg=_BG_DEEP)
    top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=42); top.pack(fill=tk.X)
    tk.Label(top, text="🤖 直接复制这段 Prompt 发给多个 AI 交叉验证",
             bg=_BG_TOOLBAR, fg=_FG_PURPLE, font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, padx=12, pady=8)
    def _copy():
        dlg.clipboard_clear(); dlg.clipboard_append(_AI_PROMPT)
        copy_btn.config(text="✅ 已复制!"); dlg.after(1500, lambda: copy_btn.config(text="📋 复制"))
    copy_btn = tk.Button(top, text="📋 复制", command=_copy, bg=_BG_PANEL, fg=_FG_GOLD,
                         relief=tk.FLAT, font=("TkDefaultFont", 11, "bold"), padx=10, pady=3)
    copy_btn.pack(side=tk.RIGHT, padx=12)
    st = tk.Text(dlg, wrap="word", bg=_BG_DEEP, fg=_FG_TEXT, font=("Menlo", 11),
                 relief=tk.FLAT, padx=12, pady=10, state=tk.DISABLED)
    st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    st.config(state=tk.NORMAL); st.insert("1.0", _AI_PROMPT); st.config(state=tk.DISABLED)


__all__ = ["show_emotion_freeze"]
