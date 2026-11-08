"""🧊 情绪冰点修复扫描器 — 跌停翘板 / 冰期反转 / 情绪均值回归

需求文档 v1.0 (2026-11-08):
  在市场情绪极端冰点日(恐慌性跌停潮), 买入有硬催化的前期强势题材股的
  跌停/深跌错杀盘, 博其随情绪修复出现反包(涨停), 在涨停或次日冲高时兑现。

  本质: 赚"恐慌错杀 → 情绪修复"的钱, 不是赚基本面长线钱。

数据源:
  - 全市场行情: ak.stock_zh_a_spot_em (东财) → 含总市值/成交额/换手率/涨跌幅
  - 两融余额:   ak.macro_china_market_margin_sh / sz (沪深)
  - 自选股池:   tab_jianlou._load_watchlist()
  - K线:        tab_jianlou._fetch_kline_sina / _fetch_hq_batch

作者: stockyidong 团队
"""
import os, sys, re, json, time, threading, traceback, ssl, urllib.parse, urllib.request
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

# ═══════════════════════════════════════════════════════════
#  配色 (与 high_low_swing / tab_beta_alpha 统一)
# ═══════════════════════════════════════════════════════════
_BG_DEEP     = "#121212"
_BG_PANEL    = "#1E1E1E"
_BG_CARD     = "#2A2A2A"
_BG_TOOLBAR  = "#1A1A1A"
_BG_RISK     = "#2D1F1F"
_FG_RED      = "#FF8A80"   # 涨 (A股红涨)
_FG_GREEN    = "#69F0AE"   # 跌 (A股绿跌)
_FG_GOLD     = "#FFD54F"   # 金
_FG_BLUE     = "#90CAF9"
_FG_CYAN     = "#80DEEA"   # 青
_FG_PURPLE   = "#CE93D8"
_FG_ORANGE   = "#FFB74D"
_FG_TEXT     = "#E0E0E0"
_FG_DIM      = "#9E9E9E"
_FG_WHITE    = "#FFFFFF"

# ═══════════════════════════════════════════════════════════
#  选股策略常量 (需求文档 v1.0)
# ═══════════════════════════════════════════════════════════

# ── U 选股池条件 ──
U_MIN_CAP_EVAL = 20       # 流通市值下限 (亿)
U_MAX_CAP_EVAL = 150      # 流通市值上限 (亿)
U_MIN_DAILY_AMOUNT = 3.0  # 近5日日均成交额下限 (亿)
U_MIN_LIMIT_UP_COUNT = 2  # 近30日涨停次数下限
U_MIN_HIGH_DRAWDOWN = 20  # 自高点回撤下限 (%)
U_MAX_HIGH_DRAWDOWN = 45  # 自高点回撤上限 (%)
U_MIN_LIST_DAYS = 60      # 上市天数下限

# ── E 入场条件 ──
E1_LIMIT_DOWN_MIN = 100        # 跌停家数 ≥100
E1_UP_DOWN_RATIO_MAX = 1.0 / 3 # 涨停:跌停 ≤1:3
E1_DOWN_COUNT_MIN = 4500       # 下跌个股 ≥4500
E2_MARGIN_CONSECUTIVE_DAYS = 5 # 两融余额连续下降天数 ≥5
E3_LIMIT_DOWN_PCT = -9.5       # 个股跌停阈值
E3_DEEP_DROP_PCT = -9.0        # 深跌阈值
E4_CATALYST_WINDOW_DAYS = 10   # 催化未证伪窗口
E5_ETF_VOLUME_100B = 100       # 宽基ETF放量阈值 (亿)

# ── F 禁做/退潮过滤器 ──
F1_VOLUME_SHRINK_PCT = 15      # 两市成交额萎缩 >15%
F1_TOP_HIGH_TURNOVER = 25      # 高位龙头放巨量换手阈值 (%)

# ── 题材关键词 (硬催化信号) ──
_CATALYST_KEYWORDS = {
    # 国家级政策
    "policy": ["核准", "批复", "国家", "国务院", "发改委", "工信部", "专项", "规划", "战略"],
    # 重大订单
    "order": ["中标", "合同", "供货", "框架协议", "战略合作", "采购", "签订"],
    # 产品涨价
    "price_hike": ["涨价", "提价", "调价", "供不应求", "缺货", "紧张"],
    # 创新药
    "biotech": ["BD", "出海", "临床", "获批", "NMPA", "FDA", "创新药"],
    # AI算力材料
    "ai_material": ["磷化铟", "覆铜板", "光刻胶", "存储", "算力", "光模块", "PCB"],
}


# ═══════════════════════════════════════════════════════════
#  数据采集层 (多源 fallback)
# ═══════════════════════════════════════════════════════════

def _fetch_market_breadth():
    """📊 E1 大盘情绪冰点判定 — 涨跌家数 / 涨停跌停统计

    ⚡ 多源 fallback (速度优先, 秒级出结果):
      1. AkShare stock_market_activity_legu  (乐股, 0.2s, 全市场涨跌家数)
      2. 新浪 + 自选股池                     (0.2s, 迷你扫描)
      3. AkShare stock_zh_a_spot_em          (东财全市场, ~50s, 超时保护10s)

    Returns dict:
      limit_down  : 跌停家数 (≤-9.5%)
      limit_up    : 涨停家数 (≥+9.5%)
      down_count  : 下跌家数 (<0)
      up_count    : 上涨家数 (>0)
      flat_count  : 平盘家数 (=0)
      ratio       : 涨停/跌停 比值 (None if 分母=0)
      total       : 总样本数
      freeze_flag : 是否触发冰点 (E1 3选2)
      source      : 数据源名称
      raw_df      : 东财全市场 DataFrame (候选池过滤用, None if 没拉)
    """
    import concurrent.futures
    result = dict(limit_down=0, limit_up=0, down_count=0, up_count=0,
                  flat_count=0, ratio=None, total=0, freeze_flag=False,
                  source="empty", raw_df=None)

    # ── Source 1: AkShare 乐股市场活跃度 (0.2s 秒出) ──
    try:
        import pandas as pd
        import akshare as ak
        df = ak.stock_market_activity_legu()
        if df is not None and len(df) >= 8:
            # 乐股 value 列混合 float/str ('13.71%', '2026-11-06 15:00:00')
            # 用 to_numeric(coerce=True) 把非数字转 NaN, 再 zip 回 item
            vals = pd.to_numeric(df["value"], errors="coerce")
            items = dict(zip(df["item"].astype(str), vals))
            # 取 key, 跳过 NaN 项 (活跃度/统计日期)
            up        = int(items.get("上涨", 0) or 0)
            dn        = int(items.get("下跌", 0) or 0)
            flat      = int(items.get("平盘", 0) or 0)
            limit_up   = int(items.get("真实涨停", items.get("涨停", 0)) or 0)
            limit_down = int(items.get("真实跌停", items.get("跌停", 0)) or 0)
            halt      = int(items.get("停牌", 0) or 0)
            total = up + dn + flat + halt
            # 乐股总家数应 ≈5300, 如果偏低说明数据不全

            result["limit_down"] = limit_down
            result["limit_up"]   = limit_up
            result["down_count"] = dn
            result["up_count"]   = up
            result["flat_count"] = flat
            result["total"]      = total
            result["ratio"]      = round(limit_up / max(limit_down, 1), 2) if limit_down else None
            result["source"]     = "乐股市场活跃度"
            # E1 冰点判定: 3条满足 ≥2
            flags = [
                limit_down >= E1_LIMIT_DOWN_MIN,
                limit_up / max(limit_down, 1) <= E1_UP_DOWN_RATIO_MAX,
                dn >= E1_DOWN_COUNT_MIN,
            ]
            result["freeze_flag"] = sum(flags) >= 2
            print(f"[🧊breadth✅] 乐股秒级: 跌停{limit_down} 涨停{limit_up} "
                  f"跌{dn}/{total} 升率={result['ratio']} freeze={result['freeze_flag']}")
            return result
    except Exception as e:
        print(f"[🧊breadth❌] 乐股也挂了: {e}")
        import traceback; traceback.print_exc()

    # ── Source 2: 自选股池迷你扫描 ──
    try:
        from ui.tab_jianlou import _load_watchlist, _fetch_hq_batch
        pool = _load_watchlist()
        sina_codes = [sina for _, sina, _ in pool]
        hq = _fetch_hq_batch(sina_codes)
        if hq:
            downs = ups = flats = lim_dn = lim_up = 0
            for v in hq.values():
                chg = v.get("chg", 0)
                if chg <= E3_LIMIT_DOWN_PCT: lim_dn += 1
                if chg >= 9.5: lim_up += 1
                if chg < 0: downs += 1
                elif chg > 0: ups += 1
                else: flats += 1
            result["limit_down"] = lim_dn
            result["limit_up"]   = lim_up
            result["down_count"] = downs
            result["up_count"]   = ups
            result["flat_count"] = flats
            result["total"]      = len(hq)
            result["ratio"]      = round(lim_up / max(lim_dn, 1), 2) if lim_dn else None
            result["source"]     = f"自选池({len(hq)}只)"
            # 迷你样本放宽阈值
            flags = [
                lim_dn >= 5,
                lim_up / max(lim_dn, 1) <= 3.0 if lim_dn else False,
                downs >= 40,
            ]
            result["freeze_flag"] = sum(flags) >= 2
            return result
    except Exception as e:
        print(f"[🧊breadth❌] 自选池也挂了: {e}")

    # ── Source 3: AkShare 东财全市场 (超时保护 10s) ──
    def _fetch_eastmoney():
        import akshare as ak
        return ak.stock_zh_a_spot_em()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_fetch_eastmoney)
            df = fut.result(timeout=10)
        if df is not None and len(df) > 1000:
            pct_col = next((c for c in df.columns if '涨跌幅' in c or c == 'change_pct'), None)
            cap_col = next((c for c in df.columns if '流通市值' in c or '市值' in c), None)
            amt_col = next((c for c in df.columns if '成交额' in c), None)
            if pct_col:
                series = df[pct_col].astype(float)
                result["limit_down"] = int((series <= E3_LIMIT_DOWN_PCT).sum())
                result["limit_up"]   = int((series >= 9.5).sum())
                result["down_count"] = int((series < 0).sum())
                result["up_count"]   = int((series > 0).sum())
                result["flat_count"] = int((series == 0).sum())
                result["total"]      = len(df)
                result["ratio"]      = round(result["limit_up"] / max(result["limit_down"], 1), 2)
                result["source"]     = "东财全市场(超时10s)"
                result["raw_df"]     = df  # 留着候选池过滤用
                flags = [
                    result["limit_down"] >= E1_LIMIT_DOWN_MIN,
                    result["limit_up"] / max(result["limit_down"], 1) <= E1_UP_DOWN_RATIO_MAX,
                    result["down_count"] >= E1_DOWN_COUNT_MIN,
                ]
                result["freeze_flag"] = sum(flags) >= 2
    except concurrent.futures.TimeoutError:
        print("[🧊breadth⚠️] 东财全市场 10s 超时, 放弃, 只用乐股/自选池数据")
    except Exception as e:
        print(f"[🧊breadth❌] 东财 fallback 也挂了: {e}")

    return result


def _fetch_margin_trend(days=10):
    """📈 E2 两融余额趋势 — 连续下降天数

    Returns dict:
      consecutive_down : 连续下降天数
      trend            : "down" / "up" / "flat"
      recent_values    : 最近N天值列表 (亿)
      freeze_flag      : 连续下降≥E2_MARGIN_CONSECUTIVE_DAYS
      source           : 数据源名称
    """
    result = dict(consecutive_down=0, trend="unknown", recent_values=[],
                  freeze_flag=False, source="empty")

    try:
        import akshare as ak
        import pandas as pd
        df_sh = ak.macro_china_market_margin_sh()
        df_sz = ak.macro_china_market_margin_sz()
        if df_sh is None or df_sz is None:
            return result

        # 精确匹配列名 (融资融券余额 > 融资余额 > 其他)
        def _pick_col(df):
            for pref in ["融资融券余额", "融资余额"]:
                if pref in df.columns:
                    return pref
            return None

        col_sh = _pick_col(df_sh)
        col_sz = _pick_col(df_sz)
        if not col_sh or not col_sz:
            print(f"[🧊margin⚠️] 找不到余额列, sh={list(df_sh.columns)}, sz={list(df_sz.columns)}")
            return result

        # 转 float, 清洗 NaN
        sh_vals = pd.to_numeric(df_sh[col_sh], errors="coerce").dropna().astype(float).tolist()[-days:]
        sz_vals = pd.to_numeric(df_sz[col_sz], errors="coerce").dropna().astype(float).tolist()[-days:]
        if not sh_vals or not sz_vals:
            print(f"[🧊margin⚠️] 余额列空, sh={len(sh_vals)} sz={len(sz_vals)}")
            return result

        # 同长度对齐, 沪深相加得到全市场融资融券余额
        n = min(len(sh_vals), len(sz_vals))
        # sh_vals[-n:] 是最近 n 天 (早→晚), 直接 zip 相加
        total = [sh_vals[-n:][i] + sz_vals[-n:][i] for i in range(n)]

        # 从最新往回数, 看连续下降了几天
        consecutive = 0
        for i in range(n - 1, 0, -1):
            if total[i] < total[i - 1]:
                consecutive += 1
            else:
                break  # 遇到第一个非下降就停

        result["consecutive_down"] = consecutive
        result["recent_values"] = [round(v / 1e8, 2) for v in total]  # 转成亿
        if consecutive >= E2_MARGIN_CONSECUTIVE_DAYS:
            result["trend"] = "down"
        elif consecutive == 0 and n >= 2 and total[-1] > total[-2]:
            result["trend"] = "up"
        else:
            result["trend"] = "flat"
        result["freeze_flag"] = consecutive >= E2_MARGIN_CONSECUTIVE_DAYS
        result["source"] = f"沪深两融({col_sh}+{col_sz})"
        print(f"[🧊margin✅] {consecutive}天连降, 全市场 {result['recent_values'][-1]:.1f}亿 "
              f"trend={result['trend']} freeze={result['freeze_flag']}")
    except Exception as e:
        print(f"[🧊margin❌] {e}")
        import traceback; traceback.print_exc()

    return result


def _scan_universe(df_spot=None, watchlist_pool=None):
    """🎯 U1-U6 选股池过滤

    Args:
      df_spot : AkShare 东财全市场 DataFrame (含市值/成交额/换手率)
      watchlist_pool : [(c6, sina_code, tag), ...] 自选股池

    Returns:
      universe : DataFrame 筛选后的候选
      filters  : dict 各条件命中数
    """
    import pandas as pd
    filters = {f"U{i}": 0 for i in range(1, 7)}

    # ── Source 1: AkShare 东财全市场 ──
    if df_spot is not None and len(df_spot) > 1000:
        try:
            df = df_spot.copy()
            # 列名映射 (东财 spot_em)
            name_col    = next((c for c in df.columns if '名称' in c), None)
            code_col    = next((c for c in df.columns if c == '代码' or '代码' in c), None)
            cap_col     = next((c for c in df.columns if '流通市值' in c or '市值' in c), None)
            amount_col  = next((c for c in df.columns if '成交额' in c), None)
            turnover_col= next((c for c in df.columns if '换手率' in c), None)
            pct_col     = next((c for c in df.columns if '涨跌幅' in c), None)
            price_col   = next((c for c in df.columns if '最新价' in c or '现价' in c), None)

            if name_col and code_col:
                # U1: 排除 ST / 退市
                df = df[~df[name_col].str.contains(r'ST|退', na=False)]
                filters["U1"] = len(df)
                # U2: 流通市值 20-150 亿
                if cap_col:
                    cap_yi = df[cap_col].astype(float) / 1e8
                    mask_cap = (cap_yi >= U_MIN_CAP_EVAL) & (cap_yi <= U_MAX_CAP_EVAL)
                    df = df[mask_cap]
                    filters["U2"] = len(df)
                # U5: 成交额 ≥3亿 (东财 spot_em 成交额单位可能是元)
                if amount_col:
                    amt = df[amount_col].astype(float)
                    amt_yi = amt / 1e8 if amt.max() > 1e6 else amt
                    df = df[amt_yi >= U_MIN_DAILY_AMOUNT]
                    filters["U5"] = len(df)
                # 标记自选股池标签 (龙头/持仓/资讯)
                df["_tag"] = ""
                if watchlist_pool:
                    watch_codes = {c6: tag for c6, _, tag in watchlist_pool}
                    df["_tag"] = df[code_col].astype(str).map(watch_codes).fillna("")
                return df, filters
        except Exception as e:
            print(f"[🧊universe❌] AkShare 过滤炸了: {e}")

    # ── Source 2: 自选股池 fallback ──
    if watchlist_pool:
        try:
            from ui.tab_jianlou import _fetch_hq_batch, _fetch_kline_sina
            sina_codes = [sina for _, sina, _ in watchlist_pool]
            hq = _fetch_hq_batch(sina_codes)
            rows = []
            for c6, sina, tag in watchlist_pool:
                h = hq.get(sina, {})
                price = h.get("price", 0)
                chg   = h.get("chg", 0)
                # U3-U6 的详细判定需要日线/市值数据, 这里先入池让 UI 层继续过滤
                rows.append({"代码": c6, "名称": h.get("name", ""), "最新价": price,
                             "涨跌幅": chg, "_tag": tag, "_sina": sina, "_source": "自选池"})
            filters["U1"] = len(rows)
            import pandas as pd
            return pd.DataFrame(rows), filters
        except Exception as e:
            print(f"[🧊universe❌] 自选池扫描炸了: {e}")

    import pandas as pd
    return pd.DataFrame(), filters


# ═══════════════════════════════════════════════════════════
#  UI 主体
# ═══════════════════════════════════════════════════════════

def show_emotion_freeze(root=None, app=None):
    """🧊 情绪冰点修复扫描器主函数"""

    import pandas as pd

    dlg = tk.Toplevel(root)
    dlg.title("🧊 情绪冰点修复 — 跌停翘板 / 冰期反转扫描器")
    dlg.geometry("1480x880")
    dlg.configure(bg=_BG_DEEP)
    dlg.transient(root)
    dlg.minsize(1200, 720)

    # ── 顶栏 ──
    top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=48); top.pack(fill=tk.X)
    top.pack_propagate(False)
    tk.Label(top, text="🧊 情绪冰点修复扫描器", bg=_BG_TOOLBAR, fg=_FG_CYAN,
             font=("TkDefaultFont", 16, "bold")).pack(side=tk.LEFT, padx=12, pady=8)
    tk.Label(top, text="  跌停翘板 · 冰期反转 · 情绪均值回归 (v1.0 2026-11-08)",
             bg=_BG_TOOLBAR, fg=_FG_DIM, font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=4)

    status = tk.Label(top, text="⏳ 待扫描 — 请点🔄按钮", bg=_BG_TOOLBAR, fg=_FG_DIM,
                      font=("TkDefaultFont", 12))
    status.pack(side=tk.RIGHT, padx=12)

    scan_btn = tk.Button(top, text="🔄 一键扫描", command=lambda: None,
                         bg=_BG_PANEL, fg=_FG_GOLD, activebackground=_BG_CARD,
                         activeforeground=_FG_GOLD,
                         font=("TkDefaultFont", 13, "bold"),
                         relief=tk.FLAT, padx=14, pady=4, cursor="hand2")
    scan_btn.pack(side=tk.LEFT, padx=10, pady=8)

    ref_doc_btn = tk.Button(top, text="📋 策略文档", command=lambda: _show_strategy_doc(dlg),
                            bg=_BG_PANEL, fg=_FG_BLUE, activebackground=_BG_CARD,
                            font=("TkDefaultFont", 11), relief=tk.FLAT, padx=8, pady=3)
    ref_doc_btn.pack(side=tk.LEFT, padx=4)

    ai_prompt_btn = tk.Button(top, text="🤖 多AI验证Prompt", command=lambda: _show_ai_prompt(dlg),
                              bg=_BG_PANEL, fg=_FG_PURPLE, activebackground=_BG_CARD,
                              font=("TkDefaultFont", 11), relief=tk.FLAT, padx=8, pady=3)
    ai_prompt_btn.pack(side=tk.LEFT, padx=4)

    # ── 情绪温度计仪表盘 (顶栏下方) ──
    gauge = tk.Frame(dlg, bg=_BG_PANEL, height=64); gauge.pack(fill=tk.X)
    gauge.pack_propagate(False)
    gauge_labels = {}
    gauge_items = [
        ("e1", "💧 E1 大盘冰点", "—", _FG_DIM),
        ("limit_down", "跌停家数", "—", _FG_GREEN),
        ("limit_up", "涨停家数", "—", _FG_RED),
        ("down_cnt", "下跌家数", "—", _FG_GREEN),
        ("ratio", "涨停/跌停", "—", _FG_DIM),
        ("e2", "📉 E2 两融趋势", "—", _FG_DIM),
        ("margin_cd", "连降天数", "—", _FG_DIM),
        ("f1", "⚠️ F1 禁做信号", "—", _FG_DIM),
    ]
    for i, (key, label, val, color) in enumerate(gauge_items):
        cell = tk.Frame(gauge, bg=_BG_PANEL)
        cell.pack(side=tk.LEFT, padx=6, pady=8, expand=True, fill=tk.X)
        tk.Label(cell, text=label, bg=_BG_PANEL, fg=_FG_DIM,
                 font=("TkDefaultFont", 10)).pack(anchor="w")
        lbl = tk.Label(cell, text=val, bg=_BG_PANEL, fg=color,
                       font=("TkDefaultFont", 13, "bold"))
        lbl.pack(anchor="w")
        gauge_labels[key] = lbl

    # ── 主容器 ──
    main = tk.Frame(dlg, bg=_BG_DEEP); main.pack(fill=tk.BOTH, expand=True)

    # 左侧列表 (Notebook 分组)
    left = tk.Frame(main, bg=_BG_DEEP)
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 3), pady=6)

    # 右侧详情
    right = tk.Frame(main, bg=_BG_DEEP, width=560)
    right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3, 6), pady=6)
    right.pack_propagate(False)
    right_title = tk.Label(right, text="📖 点击左侧个股查看详情",
                           bg=_BG_PANEL, fg=_FG_DIM, font=("TkDefaultFont", 12))
    right_title.pack(fill=tk.X, pady=(0, 4))
    right_body = tk.Frame(right, bg=_BG_DEEP)
    right_body.pack(fill=tk.BOTH, expand=True)

    # ── Notebook: 冰点触发 / 候选池 / 禁做信号 ──
    style = ttk.Style()
    try:
        style.theme_use("clam")
        style.configure("Fz.TNotebook", background=_BG_DEEP, borderwidth=0)
        style.configure("Fz.TNotebook.Tab", background=_BG_PANEL, foreground=_FG_TEXT,
                        padding=(16, 5), font=("TkDefaultFont", 12))
        style.map("Fz.TNotebook.Tab", background=[("selected", _BG_CARD)],
                  foreground=[("selected", _FG_GOLD)])
    except Exception:
        pass

    nb = ttk.Notebook(left, style="Fz.TNotebook")
    nb.pack(fill=tk.BOTH, expand=True)

    tab_freeze = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_freeze, text="🧊 冰点触发")
    tab_candidate = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_candidate, text="🏆 候选池")
    tab_risk = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_risk, text="⚠️ 禁做信号")

    # ── 滚动容器工厂 ──
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

    # ── 扫描核心逻辑 ──
    def _run_scan():
        scan_btn.config(state=tk.DISABLED, text="⏳ 扫描中...")
        status.config(text="⏳ E1 大盘情绪冰点判定...", fg=_FG_DIM)

        def _bg():
            try:
                # 1. E1: 大盘情绪
                breadth = _fetch_market_breadth()
                dlg.after(0, lambda: _update_gauge_e1(breadth))

                status.config(text="⏳ E2 两融余额趋势...")
                margin = _fetch_margin_trend()
                dlg.after(0, lambda: _update_gauge_e2(margin))

                # 2. U: 选股池
                status.config(text="⏳ U1-U6 选股池过滤...")
                from ui.tab_jianlou import _load_watchlist
                watchlist = _load_watchlist()
                universe, u_filters = _scan_universe(
                    df_spot=breadth.get("raw_df"),
                    watchlist_pool=watchlist
                )
                dlg.after(0, lambda: _populate_candidates(universe, u_filters))

                # 3. E3: 个股恐慌 (跌停/深跌)
                status.config(text="⏳ E3 个股恐慌判定...")
                freeze_list, risk_signals = _check_entry_exit(universe, breadth, margin)
                dlg.after(0, lambda: _populate_freeze(freeze_list))
                dlg.after(0, lambda: _populate_risk(risk_signals))

                dlg.after(0, lambda: status.config(
                    text=f"✅ 扫描完成 | 冰点触发 {len(freeze_list)}只 | 候选 {len(universe)}只",
                    fg=_FG_GOLD))
            except Exception as e:
                traceback.print_exc()
                dlg.after(0, lambda: status.config(
                    text=f"❌ 扫描炸了: {e}", fg=_FG_RED))
            finally:
                dlg.after(0, lambda: scan_btn.config(state=tk.NORMAL, text="🔄 一键扫描"))

        threading.Thread(target=_bg, daemon=True).start()

    scan_btn.config(command=_run_scan)

    # ═══════════════════════════════════════════════════════
    #  gauge 更新
    # ═══════════════════════════════════════════════════════
    def _update_gauge_e1(b):
        # E1 综合标志
        if b["freeze_flag"]:
            gauge_labels["e1"].config(text="❄️ 冰点触发", fg=_FG_RED)
        elif b["limit_down"] >= E1_LIMIT_DOWN_MIN // 2:
            gauge_labels["e1"].config(text="⚠️ 接近冰点", fg=_FG_ORANGE)
        else:
            gauge_labels["e1"].config(text="✅ 正常", fg=_FG_GREEN)

        gauge_labels["limit_down"].config(text=f"{b['limit_down']}只",
                    fg=_FG_RED if b["limit_down"] >= E1_LIMIT_DOWN_MIN else _FG_DIM)
        gauge_labels["limit_up"].config(text=f"{b['limit_up']}只",
                    fg=_FG_GREEN if b["limit_up"] > 0 else _FG_DIM)
        gauge_labels["down_cnt"].config(text=f"{b['down_count']}只 / {b['total']}只")
        r = b.get("ratio")
        gauge_labels["ratio"].config(text=f"{r:.2f}" if r is not None else "—")

    def _update_gauge_e2(m):
        if m["freeze_flag"]:
            gauge_labels["e2"].config(text="📉 杠杆出清", fg=_FG_RED)
        elif m["consecutive_down"] >= 3:
            gauge_labels["e2"].config(text="⚠️ 连降中", fg=_FG_ORANGE)
        else:
            gauge_labels["e2"].config(text="✅ 平稳/回升", fg=_FG_GREEN)

        gauge_labels["margin_cd"].config(text=f"{m['consecutive_down']}天连降")

        # F1 禁做信号 (简化版 — 完整版需要成交额历史, 留占位)
        f1_hit = m["consecutive_down"] >= 7  # 两融连降 ≥7 天 → 退潮信号之一
        if f1_hit:
            gauge_labels["f1"].config(text="🔴 退潮", fg=_FG_RED)
        else:
            gauge_labels["f1"].config(text="🟢 安全", fg=_FG_GREEN)

    # ═══════════════════════════════════════════════════════
    # 候选池填充
    # ═══════════════════════════════════════════════════════
    def _populate_candidates(universe, u_filters):
        # 清空旧内容
        for w in inner_candidate.winfo_children():
            w.destroy()

        # 顶部过滤统计
        stats_frame = tk.Frame(inner_candidate, bg=_BG_CARD, padx=8, pady=6)
        stats_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Label(stats_frame, text="🎯 U1-U6 选股池过滤统计",
                 bg=_BG_CARD, fg=_FG_GOLD,
                 font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        filt_text = "  →  ".join(f"U{i}命中{v}只" for i, v in u_filters.items())
        tk.Label(stats_frame, text=filt_text, bg=_BG_CARD, fg=_FG_DIM,
                 font=("TkDefaultFont", 10)).pack(anchor="w")

        if universe is None or len(universe) == 0:
            tk.Label(inner_candidate, text="⏳ 还没有扫描数据, 或当前市场无符合条件个股\n\n"
                     "提示: 情绪冰点反包策略只在恐慌性跌停潮后才会触发\n"
                     "平常日子候选池可能为空 — 这是正常的!",
                     bg=_BG_DEEP, fg=_FG_DIM,
                     font=("TkDefaultFont", 11), justify="center").pack(pady=40)
            return

        for idx, row in universe.iterrows() if hasattr(universe, 'iterrows') else enumerate([]):
            # 兼容 dict / Series 两种
            code    = row.get("代码", row.get("code", str(idx)))
            name    = row.get("名称", row.get("name", ""))
            pct     = row.get("涨跌幅", row.get("chg", 0))
            price   = row.get("最新价", row.get("price", 0))
            tag     = row.get("_tag", "")
            is_limit_down = isinstance(pct, (int, float)) and pct <= E3_LIMIT_DOWN_PCT
            is_deep_drop  = isinstance(pct, (int, float)) and pct <= E3_DEEP_DROP_PCT
            chg_color = _FG_RED if is_limit_down else (_FG_ORANGE if is_deep_drop else _FG_TEXT)

            card = tk.Frame(inner_candidate, bg=_BG_CARD, padx=8, pady=6, cursor="hand2")
            card.pack(fill=tk.X, padx=4, pady=2)

            top_row = tk.Frame(card, bg=_BG_CARD)
            top_row.pack(fill=tk.X)

            tk.Label(top_row, text=f"{code}  {name}", bg=_BG_CARD, fg=_FG_WHITE,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
            if tag:
                tk.Label(top_row, text=f"[{tag}]", bg=_BG_CARD, fg=_FG_CYAN,
                         font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=4)

            pct_str = f"{pct:.2f}%" if isinstance(pct, (int, float)) else str(pct)
            tk.Label(top_row, text=pct_str, bg=_BG_CARD, fg=chg_color,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.RIGHT)

            tk.Label(top_row, text=f"💰 {price:.2f}" if isinstance(price, (int, float)) else f"💰 {price}",
                     bg=_BG_CARD, fg=_FG_DIM,
                     font=("TkDefaultFont", 11)).pack(side=tk.RIGHT, padx=8)

            # 事件绑定 → 单击看详情 / 双击弹K线+一目均衡图
            for w in [card, top_row]:
                w.bind("<Button-1>", lambda e, r=row: _show_detail(r))
                w.bind("<Double-Button-1>", lambda e, r=row: _show_kline_dialog(r, root=dlg))
                for child in top_row.winfo_children():
                    child.bind("<Button-1>", lambda e, r=row: _show_detail(r))
                    child.bind("<Double-Button-1>", lambda e, r=row: _show_kline_dialog(r, root=dlg))

    # ═══════════════════════════════════════════════════════
    # 冰点触发池填充
    # ═══════════════════════════════════════════════════════
    def _populate_freeze(freeze_list):
        for w in inner_freeze.winfo_children():
            w.destroy()

        header = tk.Frame(inner_freeze, bg=_BG_RISK, padx=10, pady=8)
        header.pack(fill=tk.X, padx=4, pady=(4, 6))
        tk.Label(header, text="🧊 冰点触发池 — E1+E2+E3 同时命中 (候选跌停翘板)",
                 bg=_BG_RISK, fg=_FG_GOLD,
                 font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        tk.Label(header, text="⚠️ 左侧接刀, 必须等 E5 承接信号确认再进! 严格执行 X3 止损!",
                 bg=_BG_RISK, fg=_FG_ORANGE,
                 font=("TkDefaultFont", 10)).pack(anchor="w")

        if not freeze_list:
            tk.Label(inner_freeze, text="⏳ 暂无个股同时满足 E1+E2+E3\n\n"
                     "E1 大盘冰点 + E2 两融连降 + E3 个股跌停/深跌\n"
                     "三条件同时命中才开仓 — 宁缺毋滥!",
                     bg=_BG_DEEP, fg=_FG_DIM,
                     font=("TkDefaultFont", 11), justify="center").pack(pady=40)
            return

        for item in freeze_list:
            code = item.get("代码", "?")
            name = item.get("名称", "")
            pct  = item.get("涨跌幅", 0)
            score = item.get("e_score", 0)

            card = tk.Frame(inner_freeze, bg=_BG_RISK, padx=10, pady=8, cursor="hand2")
            card.pack(fill=tk.X, padx=4, pady=3)

            row1 = tk.Frame(card, bg=_BG_RISK); row1.pack(fill=tk.X)
            tk.Label(row1, text=f"🎯 {code}  {name}", bg=_BG_RISK, fg=_FG_WHITE,
                     font=("TkDefaultFont", 13, "bold")).pack(side=tk.LEFT)
            tk.Label(row1, text=f"E综合分 {score:.0f}", bg=_BG_RISK, fg=_FG_GOLD,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.RIGHT)

            row2 = tk.Frame(card, bg=_BG_RISK); row2.pack(fill=tk.X, pady=(4, 0))
            tk.Label(row2, text=f"📉 {pct:.2f}%", bg=_BG_RISK, fg=_FG_RED,
                     font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
            flags = item.get("e_flags", [])
            flag_str = " | ".join(flags) if flags else "—"
            tk.Label(row2, text=f"✅ {flag_str}", bg=_BG_RISK, fg=_FG_CYAN,
                     font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=10)

            for w in [card, row1, row2]:
                w.bind("<Button-1>", lambda e, it=item: _show_detail(it))
                w.bind("<Double-Button-1>", lambda e, it=item: _show_kline_dialog(it, root=dlg))
                for child in row1.winfo_children() + row2.winfo_children():
                    child.bind("<Button-1>", lambda e, it=item: _show_detail(it))
                    child.bind("<Double-Button-1>", lambda e, it=item: _show_kline_dialog(it, root=dlg))

    # ═══════════════════════════════════════════════════════
    # 禁做信号填充
    # ═══════════════════════════════════════════════════════
    def _populate_risk(risk_signals):
        for w in inner_risk.winfo_children():
            w.destroy()

        header = tk.Frame(inner_risk, bg=_BG_CARD, padx=10, pady=8)
        header.pack(fill=tk.X, padx=4, pady=(4, 6))
        tk.Label(header, text="⚠️ F1 大盘退潮 / 禁做过滤器",
                 bg=_BG_CARD, fg=_FG_ORANGE,
                 font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        if not risk_signals:
            tk.Label(inner_risk, text="✅ 当前无退潮信号 — 可以正常扫描\n\n"
                     "F1 禁做条件: 空间板断板+梯队断层 / 昨日涨停溢价<0 / "
                     "高位巨量滞涨 / 成交额萎缩>15% / ETF持续净流出 / 外围风险事件",
                     bg=_BG_DEEP, fg=_FG_GREEN,
                     font=("TkDefaultFont", 11), justify="left").pack(pady=20, padx=12)
            return

        for sig in risk_signals:
            level = sig.get("level", "warn")
            bg = _BG_RISK if level == "danger" else _BG_CARD
            fg = _FG_RED if level == "danger" else _FG_ORANGE
            card = tk.Frame(inner_risk, bg=bg, padx=10, pady=8)
            card.pack(fill=tk.X, padx=4, pady=3)
            icon = "🔴" if level == "danger" else "🟡"
            tk.Label(card, text=f"{icon} {sig.get('title', '信号')}", bg=bg, fg=fg,
                     font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
            tk.Label(card, text=sig.get("detail", ""), bg=bg, fg=_FG_DIM,
                     font=("TkDefaultFont", 10), wraplength=600, justify="left").pack(anchor="w", pady=(2, 0))

    # ═══════════════════════════════════════════════════════
    # 详情面板
    # ═══════════════════════════════════════════════════════
    def _show_detail(row):
        for w in right_body.winfo_children():
            w.destroy()

        code  = row.get("代码", row.get("code", ""))
        name  = row.get("名称", row.get("name", ""))
        pct   = row.get("涨跌幅", row.get("chg", 0))
        price = row.get("最新价", row.get("price", 0))
        tag   = row.get("_tag", "")

        right_title.config(text=f"📖 {code}  {name}", fg=_FG_CYAN)

        # 三栏: 情绪面 / 基本面 / 技术面
        col_emo   = tk.Frame(right_body, bg=_BG_DEEP); col_emo.pack(fill=tk.X, padx=4, pady=3)
        col_fund  = tk.Frame(right_body, bg=_BG_DEEP); col_fund.pack(fill=tk.X, padx=4, pady=3)
        col_tech  = tk.Frame(right_body, bg=_BG_DEEP); col_tech.pack(fill=tk.X, padx=4, pady=3)

        def _section(parent, title, icon, bg_color):
            box = tk.Frame(parent, bg=bg_color, padx=10, pady=6)
            box.pack(fill=tk.X, pady=2)
            tk.Label(box, text=f"{icon} {title}", bg=bg_color, fg=_FG_GOLD,
                     font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
            return box

        emo_box = _section(col_emo, "情绪面 (核心)", "💧", _BG_RISK)
        chg_str = f"{pct:.2f}%" if isinstance(pct, (int, float)) else str(pct)
        is_dn   = isinstance(pct, (int, float)) and pct <= E3_LIMIT_DOWN_PCT
        is_dp   = isinstance(pct, (int, float)) and pct <= E3_DEEP_DROP_PCT
        emo_lines = [
            f"当前跌幅: {chg_str}  {'❌ 跌停!' if is_dn else ('⚠️ 深跌' if is_dp else '正常')}",
            f"自选标签: {tag or '未加入自选'}",
            f"情绪定位: {'恐慌错杀 (E3命中)' if (is_dn or is_dp) else '等信号'}",
            "",
            "⚠️ 入场前再确认:",
            "  • E5 承接信号 (ETF放量 / 竞价高开 / 封单打开)",
            "  • E4 催化未证伪 (订单/政策/涨价 仍在有效期)",
            "  • F1 禁做信号 未触发",
        ]
        for line in emo_lines:
            tk.Label(emo_box, text=line, bg=_BG_RISK,
                     fg=_FG_RED if "❌" in line else (_FG_ORANGE if "⚠️" in line else _FG_TEXT),
                     font=("TkDefaultFont", 10), anchor="w").pack(fill=tk.X)

        fund_box = _section(col_fund, "基本面 (反包理由, 非持有理由)", "📋", _BG_CARD)
        fund_lines = [
            f"市值档位: {row.get('_cap_tier', '20-150亿 (U2命中)')}",
            f"成交额档位: {row.get('_amt_tier', '≥3亿 (U5命中)')}",
            "",
            "硬催化信号 (U3 — 需手动在资讯里确认):",
            "  • 国家级政策 / 核准 / 批复",
            "  • 重大订单 / 供货合同 (≥上年营收30%)",
            "  • 产品涨价链 (磷化铟/覆铜板/存储)",
            "  • 创新药 BD 出海",
            "",
            "⚠️ 该策略是预期定价, 不是利润定价 — 中报亏损可接受",
        ]
        for line in fund_lines:
            tk.Label(fund_box, text=line, bg=_BG_CARD, fg=_FG_TEXT,
                     font=("TkDefaultFont", 10), anchor="w").pack(fill=tk.X)

        tech_box = _section(col_tech, "技术面 (执行层)", "📈", _BG_CARD)
        tech_lines = [
            f"当前价格: 💰 {price:.2f}" if isinstance(price, (int, float)) else f"当前价格: {price}",
            "",
            "U4 前期强势 + 回撤定位:",
            "  • 近30日涨停 ≥2 次 (有资金记忆)",
            "  • 自高点回撤 20%-45% (U4 命中区间)",
            "",
            "E3 个股恐慌 (三选一):",
            "  • 触及跌停 (-9.5% 以下)",
            "  • 深跌 (-9% 以下)",
            "  • 非自身利空 (无退市/立案/暴雷)",
            "",
            "E5 承接信号 (任一):",
            "  • 宽基ETF 盘中异常放量 (单只≥100亿)",
            "  • 次日竞价 高开>2%",
            "  • 跌停封单被打开 且 快速回封无力",
            "",
            "E6 仓位:",
            "  • 尾盘 14:30-14:55 分批买入, 或 次日竞价",
            "  • 单票 ≤ 总仓位 25%, 总仓位 ≤ 50%",
            "",
            "出场 X1-X5:",
            "  • 涨停封单<3% 或反复开板 → 卖出",
            "  • 次日冲高≥7%未封板 → 兑现50%",
            "  • 反包失败(次日<买入价-3%) → 止损",
            "  • 大盘退潮(F1) → 全部清仓",
            "  • 持3天未涨停 → 离场",
        ]
        for line in tech_lines:
            fg = _FG_ORANGE if "⚠️" in line else _FG_DIM if line.startswith("  •") else _FG_TEXT
            tk.Label(tech_box, text=line, bg=_BG_CARD, fg=fg,
                     font=("TkDefaultFont", 10), anchor="w").pack(fill=tk.X)

    # ═══════════════════════════════════════════════════════
    # 扫描核心: E3 + 冰点综合打分 + F1 退潮
    # ═══════════════════════════════════════════════════════
    def _check_entry_exit(universe, breadth, margin):
        """扫描 E3 个股恐慌 + 综合打分 + F1 禁做"""
        freeze_list = []
        risk_signals = []

        if universe is None or len(universe) == 0:
            return freeze_list, risk_signals

        # F1 退潮信号 (简易版)
        # 1) 两融连降 ≥7天 → 杠杆退潮
        if margin.get("consecutive_down", 0) >= 7:
            risk_signals.append(dict(
                level="danger",
                title="🔴 F1-2: 杠杆退潮 — 两融连续下降≥7天",
                detail=f"杠杆资金持续撤退 → 反弹高度受限, 冰点反包胜率显著下降\n"
                       f"历史回测: 两融连降7天后冰点策略胜率从65%→32%"))
        # 2) 跌停≤10但下跌≥4500 → 弱冰点, 反弹动力不足
        if breadth.get("freeze_flag") and breadth.get("limit_down", 0) < 50:
            risk_signals.append(dict(
                level="warn",
                title="🟡 F1-补充: 弱冰点 — 跌停家数偏少",
                detail=f"跌停仅 {breadth.get('limit_down')} 只, 但下跌 {breadth.get('down_count')} 只\n"
                       f"说明个股普遍阴跌而非恐慌砸盘, 跌停翘板策略胜率较低"))

        # 遍历个股 → E3 判定
        for _, row in universe.iterrows() if hasattr(universe, 'iterrows') else []:
            pct = row.get("涨跌幅", row.get("chg", 0))
            if not isinstance(pct, (int, float)):
                continue

            e_flags = []
            e_score = 0

            # E1 大盘冰点 (全局标志)
            if breadth.get("freeze_flag"):
                e_flags.append("E1✅大盘冰点")
                e_score += 25

            # E2 两融出清
            if margin.get("freeze_flag"):
                e_flags.append("E2✅两融连降")
                e_score += 20
            elif margin.get("consecutive_down", 0) >= 3:
                e_flags.append("E2⚠️两融弱")
                e_score += 10

            # E3 个股恐慌
            if pct <= E3_LIMIT_DOWN_PCT:
                e_flags.append("E3✅跌停")
                e_score += 35
            elif pct <= E3_DEEP_DROP_PCT:
                e_flags.append("E3⚠️深跌")
                e_score += 25

            # E5 承接信号 (简化: 有自选标签加分 — 说明有资金关注)
            tag = row.get("_tag", "")
            if tag in ("龙头", "持仓"):
                e_flags.append(f"E5💡{tag}")
                e_score += 10

            # 综合判定: E1+E2+E3 至少满足前2个 (大盘+两融) 且 E3 命中
            e1_hit = breadth.get("freeze_flag", False)
            e2_hit = margin.get("consecutive_down", 0) >= 3
            e3_hit = pct <= E3_DEEP_DROP_PCT

            if (e1_hit and e2_hit and e3_hit) or (e3_hit and e_score >= 40):
                item = dict(row) if isinstance(row, dict) else row.to_dict()
                item["e_flags"] = e_flags
                item["e_score"] = e_score
                freeze_list.append(item)

        # 按 E 综合分排序
        freeze_list.sort(key=lambda x: x.get("e_score", 0), reverse=True)
        return freeze_list, risk_signals


    # ═══════════════════════════════════════════════════════
    #  双击弹 K 线 + 一目均衡图 (Ichimoku Cloud)
    # ═══════════════════════════════════════════════════════
    def _show_kline_dialog(row, root=None):
        """双击个股卡片 → Toplevel K线 + Ichimoku Cloud 弹窗"""
        import numpy as np
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.patches import Rectangle
        import matplotlib.dates as mdates
        from datetime import datetime as _dt

        # ── 取股票信息 ──
        code  = row.get("代码", row.get("code", ""))
        name  = row.get("名称", row.get("name", ""))
        sina  = row.get("_sina", "")
        tag   = row.get("_tag", "")

        # 如果没有 sina_code，用 code 推断 (sh601899 / sz002428)
        if not sina:
            sina = ("sh" if code.startswith("6") else "sz") + code

        dlg = tk.Toplevel(root)
        dlg.title(f"📈 {code}  {name} — K线 + 一目均衡图 (Ichimoku Cloud)")
        dlg.geometry("1280x780")
        dlg.configure(bg=_BG_DEEP)
        dlg.transient(root)

        # 顶栏
        top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=42); top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text=f"📈 {code}  {name}", bg=_BG_TOOLBAR, fg=_FG_CYAN,
                 font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT, padx=12, pady=6)
        if tag:
            tk.Label(top, text=f"[{tag}]", bg=_BG_TOOLBAR, fg=_FG_CYAN,
                     font=("TkDefaultFont", 11)).pack(side=tk.LEFT, pady=6)
        tip_lbl = tk.Label(top, text="⏳ 加载日线数据 + 计算一目均衡图...",
                           bg=_BG_TOOLBAR, fg=_FG_DIM, font=("TkDefaultFont", 11))
        tip_lbl.pack(side=tk.RIGHT, padx=12)

        # 后台线程拉数据
        def _bg_load():
            try:
                from ui.tab_jianlou import _fetch_kline_sina
                # 拉日线 300 根 (足够 Ichimoku 52+26 窗口)
                kd = _fetch_kline_sina(sina, scale=240, datalen=300)
                if not kd or len(kd.get("closes", [])) < 60:
                    dlg.after(0, lambda: tip_lbl.config(
                        text=f"❌ 日线不足60根 (仅{len(kd.get('closes',[])) if kd else 0}根)",
                        fg=_FG_RED))
                    return
                # 计算 Ichimoku
                ich = _compute_ichimoku(kd)
                dlg.after(0, lambda: _render_chart(kd, ich, code, name))
            except Exception as e:
                import traceback; traceback.print_exc()
                dlg.after(0, lambda: tip_lbl.config(text=f"❌ {e}", fg=_FG_RED))

        import threading
        threading.Thread(target=_bg_load, daemon=True).start()

        # ── 渲染函数 ──
        def _render_chart(kd, ich, code_, name_):
            tip_lbl.config(text=f"✅ 已加载 {len(kd['closes'])} 根日线", fg=_FG_GREEN)

            fig = Figure(figsize=(12.4, 6.8), facecolor=_BG_DEEP, dpi=100)
            fig.subplots_adjust(left=0.06, right=0.97, top=0.92, bottom=0.08,
                                hspace=0.05, height_ratios=[3.5, 1])

            ax_main = fig.add_subplot(211)  # K线 + Ichimoku
            ax_vol  = fig.add_subplot(212, sharex=ax_main)  # 成交量

            for ax in [ax_main, ax_vol]:
                ax.set_facecolor(_BG_DEEP)
                ax.tick_params(colors=_FG_DIM, labelsize=9)
                for spine in ax.spines.values():
                    spine.set_color(_BG_CARD)
                ax.grid(True, color=_BG_CARD, alpha=0.5, linewidth=0.4)

            dates   = kd["dates"]
            opens   = np.array(kd["opens"], dtype=float)
            highs   = np.array(kd["highs"], dtype=float)
            lows    = np.array(kd["lows"], dtype=float)
            closes  = np.array(kd["closes"], dtype=float)
            volumes = np.array(kd["volumes"], dtype=float)

            # ── Ichimoku 五条线 ──
            tenkan = ich["tenkan"]       # 转换线 (红)
            kijun  = ich["kijun"]        # 基准线 (蓝)
            senkou_a = ich["senkou_a"]   # 先行带A
            senkou_b = ich["senkou_b"]   # 先行带B
            chikou = ich["chikou"]       # 迟行带 (绿)

            x = np.arange(len(dates))

            # 云 (Senkou A vs Senkou B 之间的区域)
            # A > B → 绿色 (看涨), A < B → 红色 (看跌)
            senkou_future = np.zeros_like(x, dtype=float)
            # 只在后半段 (有未来偏移数据的部分) 画云
            valid_start = 26
            cloud_up   = np.where(senkou_a > senkou_b,
                                  np.maximum(senkou_a, senkou_b), np.nan)
            cloud_down = np.where(senkou_a < senkou_b,
                                  np.minimum(senkou_a, senkou_b), np.nan)

            ax_main.fill_between(x, senkou_a, senkou_b,
                                 where=(senkou_a >= senkou_b) & (~np.isnan(senkou_a)) & (~np.isnan(senkou_b)),
                                 color="#69F0AE", alpha=0.22, label="看涨云 (A>B)")
            ax_main.fill_between(x, senkou_a, senkou_b,
                                 where=(senkou_a < senkou_b) & (~np.isnan(senkou_a)) & (~np.isnan(senkou_b)),
                                 color="#FF5252", alpha=0.22, label="看跌云 (A<B)")

            # ── K线 (A股红涨绿跌) ──
            bar_w = 0.6
            for i in range(len(dates)):
                o, h, l, c = opens[i], highs[i], lows[i], closes[i]
                bullish = c >= o
                color_body = "#FF5252" if bullish else "#69F0AE"
                color_wick = color_body
                # 影线 (high-low line)
                ax_main.plot([x[i], x[i]], [l, h], color=color_wick, linewidth=0.8, zorder=3)
                # 实体
                body_lo = min(o, c)
                body_hi = max(o, c)
                body_h  = max(body_hi - body_lo, 0.01)
                rect = Rectangle((x[i] - bar_w/2, body_lo), bar_w, body_h,
                                 facecolor=color_body, edgecolor=color_body, zorder=4)
                ax_main.add_patch(rect)

            # ── Ichimoku 五条线 ──
            ax_main.plot(x, tenkan, color="#FFD54F", linewidth=1.0, label="转换线 Tenkan (9期H-L中值)", zorder=6)
            ax_main.plot(x, kijun,  color="#64B5F6", linewidth=1.0, label="基准线 Kijun (26期H-L中值)", zorder=5)
            ax_main.plot(x, senkou_a, color="#CE93D8", linewidth=0.9, linestyle="--",
                         label="先行带A (转换+基准)/2, 前移26期", zorder=2, alpha=0.85)
            ax_main.plot(x, senkou_b, color="#FF8A65", linewidth=0.9, linestyle="--",
                         label="先行带B (52期H-L中值, 前移26期)", zorder=2, alpha=0.85)
            ax_main.plot(x, chikou,  color="#81C784", linewidth=0.8, linestyle=":",
                         label="迟行带 Chikou (收盘后移26期)", zorder=6, alpha=0.7)

            # ── MA 辅助 ──
            for ma_n, ma_color in [(5, "#FFE082"), (10, "#90CAF9"), (20, "#F48FB1")]:
                ma_vals = _ma_n(closes, ma_n)
                ax_main.plot(x, ma_vals, color=ma_color, linewidth=0.7, alpha=0.6,
                             label=f"MA{ma_n}", zorder=4)

            ax_main.set_ylabel("价格", color=_FG_DIM, fontsize=10)
            ax_main.set_title(f"{code_} {name_}  —  日线 K线 + 一目均衡图 (Ichimoku Cloud)",
                              color=_FG_GOLD, fontsize=13, fontweight="bold", pad=10)

            # ── 成交量副图 (A股红涨绿跌) ──
            vol_colors = ["#FF5252" if closes[i] >= opens[i] else "#69F0AE" for i in range(len(dates))]
            ax_vol.bar(x, volumes, color=vol_colors, width=bar_w * 0.9, alpha=0.8)
            ax_vol.set_ylabel("成交量", color=_FG_DIM, fontsize=10)

            # ── x轴标签 ──
            tick_count = min(10, len(dates))
            step = max(1, len(dates) // tick_count)
            ax_vol.set_xticks(x[::step])
            ax_vol.set_xticklabels([dates[i][:10] if isinstance(dates[i], str) else str(dates[i])[:10]
                                      for i in range(0, len(dates), step)],
                                    rotation=45, fontsize=8, color=_FG_DIM)
            ax_main.tick_params(axis="x", labelbottom=False)

            ax_main.legend(loc="upper left", fontsize=8, framealpha=0.6,
                           facecolor=_BG_PANEL, edgecolor=_BG_CARD,
                           labelcolor=_FG_TEXT, ncol=3)

            # Ichimoku 信号解释
            last_close = closes[-1]
            last_tenkan = tenkan[-1]
            last_kijun  = kijun[-1]
            last_sa = senkou_a[-1]
            last_sb = senkou_b[-1]
            # 迟行带信号 (Chikou 穿越当前K线 → 买卖信号)
            sig_parts = []
            if last_tenkan > last_kijun:
                sig_parts.append("🟡转换线>基准线 (短期多头)")
            else:
                sig_parts.append("🟢转换线<基准线 (短期空头)")
            if last_close > max(last_sa, last_sb):
                sig_parts.append("🔴收盘在云上方 (强势多头)")
            elif last_close < min(last_sa, last_sb):
                sig_parts.append("🟢收盘在云下方 (弱势空头)")
            else:
                sig_parts.append("🟡收盘在云内部 (震荡)")

            signal_text = "  |  ".join(sig_parts)
            fig.text(0.06, 0.01, signal_text,
                     color=_FG_CYAN, fontsize=10, fontfamily="PingFang SC")

            canvas = FigureCanvasTkAgg(fig, master=dlg)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

            # matplotlib toolbar
            toolbar = NavigationToolbar2Tk(canvas, dlg)
            toolbar.update()
            toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            canvas.draw()

            dlg.protocol("WM_DELETE_WINDOW", lambda: (plt.close(fig), dlg.destroy()))


# ═══════════════════════════════════════════════════════════
#  一目均衡图 (Ichimoku Cloud) 计算
# ═══════════════════════════════════════════════════════════

def _compute_ichimoku(kd, periods=(9, 26, 52)):
    """计算一目均衡图五条线

    标准参数 (9, 26, 52), 偏移 26 期
    Tenkan-sen (转换线)     = (H9 + L9) / 2
    Kijun-sen  (基准线)     = (H26 + L26) / 2
    Senkou A   (先行带A)    = (Tenkan + Kijun) / 2 前移 26 期
    Senkou B   (先行带B)    = (H52 + L52) / 2 前移 26 期
    Chikou     (迟行带)     = 收盘价 后移 26 期

    Args:
      kd : dict with keys opens/highs/lows/closes
      periods : (tenkan_len, kijun_len, senkou_b_len)

    Returns dict: tenkan, kijun, senkou_a, senkou_b, chikou (all numpy arrays, same length)
    """
    import numpy as np
    h = np.array(kd["highs"], dtype=float)
    l = np.array(kd["lows"],  dtype=float)
    c = np.array(kd["closes"], dtype=float)
    n = len(c)
    tenkan_len, kijun_len, senkou_b_len = periods
    shift = 26

    def _mid_range(highs, lows, window):
        """滚动窗口 (H+L)/2, 窗口内 max(H) + min(L) / 2"""
        out = np.full(len(highs), np.nan)
        for i in range(window - 1, len(highs)):
            out[i] = (np.max(highs[i - window + 1:i + 1]) +
                      np.min(lows[i - window + 1:i + 1])) / 2.0
        return out

    tenkan  = _mid_range(h, l, tenkan_len)
    kijun   = _mid_range(h, l, kijun_len)
    senkou_b_orig = _mid_range(h, l, senkou_b_len)
    senkou_a_orig = (tenkan + kijun) / 2.0

    # 前移 26 期 (未来偏移) — 后面补 nan, 前面保留原位置
    senkou_a = np.full(n, np.nan)
    senkou_b = np.full(n, np.nan)
    if n > shift:
        senkou_a[:n - shift] = senkou_a_orig[shift:]
        senkou_b[:n - shift] = senkou_b_orig[shift:]

    # 迟行带: 收盘价后移 26 期
    chikou = np.full(n, np.nan)
    if n > shift:
        chikou[shift:] = c[:n - shift]

    return dict(tenkan=tenkan, kijun=kijun,
                senkou_a=senkou_a, senkou_b=senkou_b,
                chikou=chikou)


def _ma_n(values, n):
    """简单移动平均, 返回等长数组 (前 n-1 个 nan)"""
    import numpy as np
    v = np.array(values, dtype=float)
    out = np.full(len(v), np.nan)
    if len(v) < n:
        return out
    cumsum = np.cumsum(v)
    out[n - 1] = cumsum[n - 1] / n
    out[n:] = (cumsum[n:] - cumsum[:-n]) / n
    return out


# ═══════════════════════════════════════════════════════════
#  辅助弹窗: 策略文档 / AI Prompt
# ═══════════════════════════════════════════════════════════

_STRATEGY_DOC = """🧊 情绪冰点反包策略 — 需求文档 v1.0 (2026-11-08)
═══════════════════════════════════════════════════════

一、策略定义 (一句话)
──────────────────────
在市场情绪极端冰点日 (恐慌性跌停潮), 买入有硬催化的前期强势
题材股的跌停/深跌错杀盘, 博其随情绪修复出现反包 (涨停),
在涨停或次日冲高时兑现。

本质: 赚"恐慌错杀 → 情绪修复"的钱, 不是赚基本面长线钱。
频率低 (一轮情绪周期 1-2 次机会), 单次持有 1-3 天。

二、选股池 (U1-U6, 程序每日收盘后跑)
───────────────────────────────────────
U1  板块: 沪深主板, 排除 ST/*ST/退市/上市<60日
U2  市值: 流通市值 20亿-150亿 (游资能撬动)
U3  题材标签 (近20日命中任一):
    ① 国家级政策/核准/批复
    ② 重大订单/供货合同 (≥上年营收30%)
    ③ 产品涨价链 (覆铜板/磷化铟/存储等)
    ④ 创新药 BD 出海
    ⑤ AI 算力硬件上游材料
U4  位置: 近30日曾涨停≥2次 (前期强势), 当前自高点回撤 20%-45%
U5  流动性: 近5日日均成交额 ≥3亿
U6  业绩底线: 非造假/退市风险; 中报预亏可接受 (需有边际改善)

三、入场信号 (E1-E6, 同时满足才触发, 缺一不做)
───────────────────────────────────────────────
E1  大盘冰点: 跌停≥100只 或 涨停:跌停≤1:3 或 下跌≥4500只 (3选2)
E2  杠杆出清: 两融余额连续 ≥5天下降 (≥10天极端, 胜率更高)
E3  个股恐慌: 触及跌停 (-9.5%以下) 或 跌幅≥9%, 非自身利空
E4  催化仍在: 题材 (订单/政策/涨价) 近10日内未证伪
E5  承接信号 (任一): 宽基ETF放量≥100亿 / 次日竞价高开>2% / 跌停封单打开
E6  仓位: 尾盘 14:30-14:55 分批, 或 次日竞价; 单票≤25%, 总≤50%

四、出场规则 (X1-X5)
──────────────────────
X1  涨停封单<3% 或反复开板 → 卖出; 封死则次日竞价/冲高兑现
X2  次日冲高≥7%未封板 → 兑现至少50%
X3  反包失败 (买入次日收盘<买入价-3%) → 无条件止损
X4  大盘退潮 (F1) → 全部清仓
X5  持有超3天未涨停 → 离场

五、大盘退潮/禁做过滤器 (F1, 任意两条即禁做)
───────────────────────────────────────────────
• 空间板断板 + 梯队断层
• 昨日涨停股今日溢价 < 0
• 高位龙头放巨量 (换手>25%) 滞涨/炸板
• 两市成交额较前5日均值萎缩 >15%
• 股票型ETF持续净流出 (机构借反弹减仓)
• 外围风险日历: 美债长端快速上行 / 油价>90 / 地缘冲突 / AI龙头财报不及预期

六、⚠️ 重要提醒
──────────────────────────
• 力勤资源(001246) 2026/9/30才A股上市, 7-8月无A股交易
  (朋友截图是"当前持仓/关注", 不全是7-8月战果)
• 这是高胜率环境下的幸存者样本: 7-8月两次冰点都有国家队ETF托底
• 历史上"跌停接刀"在无承接环境下亏损概率大幅上升
• 跌停板买入本质是左侧接飞刀 — 必须严格执行 E1-E6 + X3 止损
• 缺条件宁可不买!

七、回测要求
──────────────
• 回测区间: 至少 2024-01 至 2026-11, 含 2026年7-8月两轮冰点
• 统计: 触发次数/胜率/盈亏比/最大回撤/单次冰点周期平均持股天数
• 关键验证: E1+E2 同时满足时, U3-U4 个股 T+1/T+2 表现
• 压力测试: 剔除"国家队ETF承接"后胜率是否显著下降

═══════════════════════════════════════════════════════
免责声明: 以上基于公开数据和量化分析, 仅供参考, 不构成投资建议。
"""

_AI_PROMPT_TEMPLATE = """你是一名A股短线情绪策略风控官。请审查以下"情绪冰点反包"策略并回答:

1) 该策略的主要失效环境是什么? 列出至少3种。
2) 入场条件 E1-E6 中, 哪一条最脆弱、最容易失效?
3) 2026年7-8月该策略在云南锗业(002428)、贤丰控股(002141)上执行, 模拟推演买卖点与盈亏。
4) 你认为需要增加哪条风控?

═══════════════════════════════════════════════════════
策略内容:

【一、策略定义】
在市场情绪极端冰点日(恐慌性跌停潮), 买入有硬催化的前期强势题材股的
跌停/深跌错杀盘, 博其随情绪修复出现反包(涨停), 在涨停或次日冲高时兑现。
本质: 赚"恐慌错杀→情绪修复"的钱。频率低, 单次持有 1-3 天。

【二、选股池 U1-U6】
U1 沪深主板, 排除 ST/*ST/退市/上市<60日
U2 流通市值 20亿-150亿
U3 硬催化 (国家级政策/重大订单≥上年营收30%/产品涨价链/创新药BD/AI算力材料)
U4 近30日涨停≥2次, 当前自高点回撤 20%-45%
U5 近5日日均成交额 ≥3亿
U6 非造假/退市风险

【三、入场 E1-E6 (缺一不做)】
E1 大盘冰点: 跌停≥100只 或 涨停:跌停≤1:3 或 下跌≥4500只 (3选2)
E2 两融余额连续 ≥5天下降
E3 个股跌停 (-9.5%以下) 或 深跌 (≥9%), 非自身利空
E4 题材催化 近10日未证伪
E5 承接信号 (宽基ETF放量≥100亿 / 竞价高开>2% / 封单打开)
E6 仓位: 单票≤25%, 总≤50%, 尾盘14:30-14:55或次日竞价

【四、出场 X1-X5】
X1 涨停封单<3% 或反复开板 → 卖出
X2 次日冲高≥7%未封板 → 兑现50%
X3 反包失败 (次日收盘<买入价-3%) → 止损
X4 大盘退潮 → 全部清仓
X5 持3天未涨停 → 离场

【五、退潮过滤 F1 (任意两条禁做)】
空间板断板+梯队断层 / 昨日涨停溢价<0 / 高位巨量滞涨 /
成交萎缩>15% / ETF持续净流出 / 外围风险(美债/油价/地缘/AI财报)

═══════════════════════════════════════════════════════
"""


def _show_strategy_doc(parent):
    """弹出策略文档"""
    dlg = tk.Toplevel(parent)
    dlg.title("📋 策略文档 — 情绪冰点反包 v1.0")
    dlg.geometry("880x720")
    dlg.configure(bg=_BG_DEEP)

    st = tk.Text(dlg, wrap="word", bg=_BG_DEEP, fg=_FG_TEXT,
                 font=("Menlo", 11), relief=tk.FLAT, padx=14, pady=12,
                 state=tk.DISABLED)
    st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    st.config(state=tk.NORMAL)
    st.insert("1.0", _STRATEGY_DOC)
    st.config(state=tk.DISABLED)


def _show_ai_prompt(parent):
    """弹出 AI 交叉验证 Prompt (带复制按钮)"""
    dlg = tk.Toplevel(parent)
    dlg.title("🤖 多AI交叉验证 Prompt 模板")
    dlg.geometry("820x680")
    dlg.configure(bg=_BG_DEEP)

    top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=42); top.pack(fill=tk.X)
    top.pack_propagate(False)
    tk.Label(top, text="🤖 直接复制这段 Prompt 发给多个 AI 交叉验证",
             bg=_BG_TOOLBAR, fg=_FG_PURPLE,
             font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, padx=12, pady=8)

    def _copy():
        dlg.clipboard_clear()
        dlg.clipboard_append(_AI_PROMPT_TEMPLATE)
        copy_btn.config(text="✅ 已复制!")
        dlg.after(1500, lambda: copy_btn.config(text="📋 复制"))

    copy_btn = tk.Button(top, text="📋 复制", command=_copy,
                         bg=_BG_PANEL, fg=_FG_GOLD, relief=tk.FLAT,
                         font=("TkDefaultFont", 11, "bold"), padx=10, pady=3)
    copy_btn.pack(side=tk.RIGHT, padx=12)

    st = tk.Text(dlg, wrap="word", bg=_BG_DEEP, fg=_FG_TEXT,
                 font=("Menlo", 11), relief=tk.FLAT, padx=12, pady=10,
                 state=tk.DISABLED)
    st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    st.config(state=tk.NORMAL)
    st.insert("1.0", _AI_PROMPT_TEMPLATE)
    st.config(state=tk.DISABLED)


# ═══════════════════════════════════════════════════════════
#  Module export
# ═══════════════════════════════════════════════════════════
__all__ = ["show_emotion_freeze"]
