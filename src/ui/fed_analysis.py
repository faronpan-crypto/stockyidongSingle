"""美联储分析 — Lazy import
加载 🏛️美联储分析 按钮时才 import, 启动不加载
"""
import warnings; warnings.filterwarnings('ignore')
import tkinter as _tk
import tkinter.ttk as _ttk
import pandas as _pd
import numpy as _np
import time as _time
import json as _json
import os as _os
import requests as _requests
import akshare as _ak

_FED_SID_TTL = {
    "DFF": 24*3600, "DFEDTARU": 24*3600, "DFEDTARL": 24*3600,
    "DGS10": 24*3600, "DGS2": 24*3600, "T10Y2Y": 24*3600,
    "DTWEXBGS": 24*3600,
    "UNRATE": 7*24*3600, "CPIAUCSL": 7*24*3600,
}

# ── 硬编码种子值 (2026-10-02 实测最新值, 界面秒渲染兜底) ──
# 格式: {sid: (最新日期, 最新值)}
_FED_SEED_LATEST = {
    "DFF":         ("2026-10-02", 3.88),    # 有效联邦基金利率
    "DFEDTARL":    ("2026-10-05", 3.75),    # 目标下限
    "DFEDTARU":    ("2026-10-05", 4.00),    # 目标上限
    "DGS10":       ("2026-10-02", 5.28),    # 10年期美债
    "DGS2":        ("2026-10-02", 4.83),    # 2年期美债
    "T10Y2Y":      ("2026-10-05", 0.47),    # 10Y-2Y 利差
    "DTWEXBGS":    ("2026-10-02", 121.38),  # 美元指数
    "UNRATE":      ("2026-09-01", 4.2),     # 失业率
    "CPIAUCSL":    ("2026-08-01", 334.13),  # CPI 指数, YoY 代码内计算 ≈ 2.9%
}

def _fed_seed_df(self, sid):
    """从硬编码种子构造只有 1 行的 DataFrame (兜底用)"""
    import pandas as pd
    s = self._FED_SEED_LATEST.get(sid)
    if s is None: return None
    df = pd.DataFrame([{"date": pd.to_datetime(s[0]), "value": s[1]}])
    return df

def _fed_cache_load(self):
    """读本地 JSON 缓存"""
    import json, os, time
    try:
        if not os.path.exists(self._FED_CACHE_PATH): return {}
        with open(self._FED_CACHE_PATH) as f:
            return json.load(f)
    except Exception: return {}

def _fed_cache_save(self, cache):
    """写 JSON 缓存"""
    import json, os, time
    try:
        os.makedirs(os.path.dirname(self._FED_CACHE_PATH), exist_ok=True)
        with open(self._FED_CACHE_PATH, "w") as f:
            json.dump(cache, f)
    except Exception: pass

def _fed_cache_get(self, sid):
    """返回 (df, state)
       state="fresh" → 缓存新鲜, 直接用
       state="stale" → 缓存过期, 显示但后台刷新
       state="seed"  → 无缓存, 用硬编码种子兜底 (只1行, 秒渲染)
    """
    import time as _t, pandas as pd
    cache = self._fed_cache_load()
    entry = cache.get(sid)
    if entry:
        # 解析缓存行
        rows = [(r[0], float(r[1])) for r in entry.get("rows", [])]
        if rows:
            df = pd.DataFrame(rows, columns=["date", "value"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            ttl = self._FED_SID_TTL.get(sid, 24*3600)
            age = _t.time() - entry.get("ts", 0)
            state = "fresh" if age <= ttl else "stale"
            return df, state
    # 无缓存或空缓存 → 返回硬编码种子
    seed = self._fed_seed_df(sid)
    if seed is not None:
        return seed, "seed"
    return None, "empty"

def _fed_cache_set(self, sid, df):
    """存 DataFrame 到缓存"""
    import time as _t, pandas as pd
    if df is None or len(df) == 0: return
    cache = self._fed_cache_load()
    rows = [[str(r[0]), float(r[1])] for r in df.values.tolist()]
    cache[sid] = {"ts": _t.time(), "rows": rows}
    self._fed_cache_save(cache)

def _fetch_fred_csv(self, sid, start_date="2018-01-01", timeout=15, use_cache=True):
    """拉FRED官方CSV (免Key) → pd.DataFrame[date, value]
    use_cache=True 时优先读本地缓存"""
    import requests, pandas as pd
    if use_cache:
        cached, fresh = self._fed_cache_get(sid)
        if cached is not None and fresh:
            return cached  # 缓存命中且新鲜, 直接返回
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start_date}"
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200: return None
        lines = r.text.strip().split('\n')
        if len(lines) < 2: return None
        rows = []
        for ln in lines[1:]:
            parts = ln.split(',')
            if len(parts) >= 2 and parts[1].strip() not in ('', '.'):
                rows.append((parts[0].strip(), float(parts[1].strip())))
        if not rows: return None
        df = pd.DataFrame(rows, columns=["date", "value"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        # 写入缓存
        if use_cache and df is not None and len(df) > 0:
            self._fed_cache_set(sid, df)
        return df
    except Exception: return None

def _get_fomc_data(self):
    """返回FOMC会议列表: [{date, action, bp, label}, ...]"""
    import pandas as pd
    FOMC_SEED = self._FOMC_SEED
    rows = []
    for d, act, bp in FOMC_SEED:
        act_cn = {"hike": "加息", "cut": "降息", "hold": "维持"}[act]
        bp_str = f"+{bp}bp" if bp > 0 else f"{bp}bp" if bp < 0 else "0bp"
        label = f"{act_cn} {bp_str}".replace("维持 0bp", "维持不变")
        rows.append({"date": d, "action": act, "bp": bp, "label": label})
    return pd.DataFrame(rows)

def _classify_fed_cycle(self, fomc_df, effr_df):
    """
    基于FOMC决策序列分类当前周期阶段:
      - 加息初期 / 加息中期 / 加息末期 (暂停前的最后一次Hike)
      - 暂停期 / 降息初期 / 降息中期 / 降息末期
    同时生成周期统计: 本轮Hike/Cut次数、累计bp、起止日期
    """
    import pandas as pd
    meetings = fomc_df[fomc_df["action"].isin(["hike", "cut"])].copy()
    if meetings.empty:
        return {"stage": "未知", "color": "#78909C", "desc": "无有效周期数据"}

    meetings["prev_action"] = meetings["action"].shift(1)
    meetings["direction"] = (meetings["action"] != meetings["prev_action"]).cumsum()
    cycles = meetings.groupby("direction")
    cycle_list = []
    for _, g in cycles:
        act = g["action"].iloc[0]
        cycle_list.append({
            "direction": "hike" if act == "hike" else "cut",
            "start_date": g["date"].iloc[0],
            "end_date": g["date"].iloc[-1],
            "count": len(g),
            "total_bp": int(g["bp"].sum()),
        })
    if not cycle_list:
        return {"stage": "未知", "color": "#78909C", "desc": "无有效周期"}

    last = cycle_list[-1]
    n = last["count"]
    if last["direction"] == "hike":
        if n <= 3:
            stage, color, desc = "加息初期", "#E53935", "刚开始加息，经济仍有韧性"
        elif n <= 6:
            stage, color, desc = "加息中期", "#FB8C00", "加息持续，关注通胀黏性"
        else:
            stage, color, desc = "加息末期", "#6D4C41", "加息次数多，警惕衰退风险"
    else:
        if n <= 3:
            stage, color, desc = "降息初期", "#43A047", "降息开始，市场流动性改善"
        elif n <= 6:
            stage, color, desc = "降息中期", "#1E88E5", "降息持续，经济修复中"
        else:
            stage, color, desc = "降息末期", "#5E35B1", "降息次数多，关注过热风险"

    # 看最近1-2次决策有没有Hold (加息后突然Hold = 可能到顶)
    recent = fomc_df.tail(3)
    has_recent_hold = any(recent["action"].values == "hold")
    if last["direction"] == "hike" and has_recent_hold:
        stage, color, desc = "加息暂停期", "#8D6E63", "加息后暂停，观察传导效果"

    return {
        "stage": stage, "color": color, "desc": desc,
        "direction": last["direction"], "cycle_count": n, "total_bp": last["total_bp"],
        "cycle_start": last["start_date"], "cycle_end": last["end_date"],
    }

def _show_fed_analysis_dialog(self):
    """🏛️ 美联储分析预测主窗口: 实时利率 + 周期判断 + FOMC决策 + 对A股传导"""
    import tkinter as _tk
    import tkinter.ttk as _ttk
    import tkinter.messagebox as _mb
    import pandas as pd
    from datetime import datetime, timedelta

    win = _tk.Toplevel(getattr(self, 'root', None) or self)
    win.title("🏛️ 美联储分析预测 — 利率·周期·传导")
    win.geometry("1280x820")
    win.configure(bg="#1A1A2E")

    # ── 顶部标题 ──
    top = _tk.Frame(win, bg="#16213E")
    top.pack(fill=_tk.X, padx=10, pady=(10, 4))
    _tk.Label(top, text="🏛️  美联储分析预测  ", font=("TkDefaultFont", 14, "bold"),
              bg="#16213E", fg="#E94560").pack(side=_tk.LEFT, padx=10, pady=8)
    _tk.Label(top, text="数据来源: FRED (免Key) · 实时更新",
              bg="#16213E", fg="#90A4AE").pack(side=_tk.RIGHT, padx=10)
    refresh_btn = _ttk.Button(top, text="🔄 刷新数据")
    refresh_btn.pack(side=_tk.RIGHT, padx=6, pady=8)

    # ── 指标卡区域 (6个) ──
    cards_frame = _tk.Frame(win, bg="#1A1A2E")
    cards_frame.pack(fill=_tk.X, padx=10, pady=(4, 6))

    def _card(parent, title, value, unit, bg, fg):
        f = _tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground="#455A64")
        f.pack(side=_tk.LEFT, expand=True, fill=_tk.X, padx=4)
        _tk.Label(f, text=title, bg=bg, fg="#90A4AE",
                  font=("TkDefaultFont", 9)).pack(pady=(8, 0))
        _tk.Label(f, text=str(value), bg=bg, fg=fg,
                  font=("TkDefaultFont", 22, "bold")).pack(pady=(0, 0))
        _tk.Label(f, text=unit, bg=bg, fg="#607D8B",
                  font=("TkDefaultFont", 9)).pack(pady=(0, 8))
        return f

    # 先放占位, 加载后更新
    card_effr   = _card(cards_frame, "有效联邦基金利率 EFFR", "—", "%", "#0F3460", "#E94560")
    card_range  = _card(cards_frame, "目标利率区间 (当前)", "—", "%", "#16213E", "#FB8C00")
    card_t10y2y = _card(cards_frame, "10Y-2Y 利差", "—", "%", "#16213E", "#43A047")
    card_dxy    = _card(cards_frame, "美元指数 DXY", "—", "", "#16213E", "#8E24AA")
    card_cpi    = _card(cards_frame, "美国 CPI YoY", "—", "%", "#16213E", "#E94560")
    card_unemp  = _card(cards_frame, "失业率 U3", "—", "%", "#16213E", "#26C6DA")

    # ── 周期信号条 ──
    cycle_frame = _tk.Frame(win, bg="#1A1A2E")
    cycle_frame.pack(fill=_tk.X, padx=10, pady=(2, 6))
    cycle_header = _tk.Label(cycle_frame, text="", bg="#16213E",
                             font=("TkDefaultFont", 14, "bold"),
                             fg="#E94560", padx=16, pady=10)
    cycle_header.pack(fill=_tk.X, side=_tk.LEFT, expand=True)
    cycle_stat = _tk.Label(cycle_frame, text="", bg="#16213E",
                           font=("TkDefaultFont", 10), fg="#B0BEC5")
    cycle_stat.pack(side=_tk.LEFT, padx=10, pady=10)

    # ── 主体 PanedWindow ──
    pw = _tk.PanedWindow(win, orient=_tk.HORIZONTAL, bg="#1A1A2E",
                         sashwidth=4, sashrelief="flat")
    pw.pack(fill=_tk.BOTH, expand=True, padx=10, pady=6)

    # 左侧: FOMC 历史决策表
    left_paned = _tk.Frame(pw, bg="#16213E")
    pw.add(left_paned)
    _tk.Label(left_paned, text="📋 FOMC 历史决策 (2018至今)",
              bg="#16213E", fg="#E94560",
              font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=8, pady=(6, 4))
    tree_frame = _tk.Frame(left_paned, bg="#16213E")
    tree_frame.pack(fill=_tk.BOTH, expand=True, padx=4, pady=4)

    cols = ("date", "action", "bp", "label")
    tree = _ttk.Treeview(tree_frame, columns=cols, show="headings", height=18)
    tree.heading("date", text="会议日期")
    tree.heading("action", text="动作")
    tree.heading("bp", text="变动(bp)")
    tree.heading("label", text="标签")
    tree.column("date", width=110, anchor="center")
    tree.column("action", width=70, anchor="center")
    tree.column("bp", width=70, anchor="center")
    tree.column("label", width=180, anchor="w")

    vsb = _ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True)
    vsb.pack(side=_tk.RIGHT, fill=_tk.Y)

    # 右侧: 对A股传导 + 策略建议 (Notebook)
    right_frame = _tk.Frame(pw, bg="#16213E")
    pw.add(right_frame)
    nb = _ttk.Notebook(right_frame)
    nb.pack(fill=_tk.BOTH, expand=True, padx=4, pady=4)

    # Tab1: 利率曲线数据
    tab_curve = _tk.Frame(nb, bg="#16213E")
    nb.add(tab_curve, text="📈 利率曲线")
    curve_text = _tk.Text(tab_curve, bg="#0F3460", fg="#ECEFF1", height=14,
                          font=("Menlo", 10), wrap="none", padx=10, pady=8,
                          borderwidth=0)
    curve_text.pack(fill=_tk.BOTH, expand=True, padx=6, pady=6)

    # Tab2: 对A股传导分析
    tab_trans = _tk.Frame(nb, bg="#16213E")
    nb.add(tab_trans, text="🌏 对A股传导")
    trans_text = _tk.Text(tab_trans, bg="#0F3460", fg="#ECEFF1", height=14,
                          font=("Menlo", 10), wrap="word", padx=10, pady=8,
                          borderwidth=0)
    trans_text.pack(fill=_tk.BOTH, expand=True, padx=6, pady=6)

    # Tab3: 策略操作建议
    tab_strat = _tk.Frame(nb, bg="#16213E")
    nb.add(tab_strat, text="🎯 策略建议")
    strat_text = _tk.Text(tab_strat, bg="#0F3460", fg="#ECEFF1", height=14,
                          font=("Menlo", 10), wrap="word", padx=10, pady=8,
                          borderwidth=0)
    strat_text.pack(fill=_tk.BOTH, expand=True, padx=6, pady=6)

    # Tab4: 历史周期对照 & 美元潮汐 & 预测框架
    tab_hist = _tk.Frame(nb, bg="#16213E")
    nb.add(tab_hist, text="📚 历史周期&预测")
    hist_text = _tk.Text(tab_hist, bg="#0F3460", fg="#ECEFF1", height=14,
                         font=("Menlo", 10), wrap="word", padx=10, pady=8,
                         borderwidth=0)
    hist_text.pack(fill=_tk.BOTH, expand=True, padx=6, pady=6)

    # ── 状态条 ──
    status = _tk.Label(win, text="⏳ 数据加载中...", bg="#1A1A2E", fg="#90A4AE",
                       anchor="w")
    status.pack(fill=_tk.X, padx=10, pady=(0, 6))

    # ═══════════════════════════════════════════════════════════════════
    # 数据加载 + 更新逻辑
    # ═══════════════════════════════════════════════════════════════════
    def _update_card(f, val, unit, fg_override=None):
        """更新指标卡的数值Label"""
        for child in f.winfo_children():
            try:
                txt = child.cget("text")
                if txt.startswith("—") or (isinstance(val, str) and txt != "—" and txt != unit):
                    pass
            except: continue
            try:
                sz = child.cget("font")[1] if isinstance(child.cget("font"), tuple) else 12
            except: continue
            if sz >= 18:  # 数值行
                child.configure(text=str(val) if not isinstance(val, float) else f"{val:.2f}",
                                fg=fg_override or child.cget("fg"))
            elif sz <= 10:  # 单位行
                child.configure(text=unit)

    def _load_data(force=False):
        """加载数据: 默认先秒读缓存显示, 再串行刷新过期序列; force=True 强制全量网络"""
        import threading, traceback
        FRED_SIDS = ["DFF", "DFEDTARU", "DFEDTARL", "DGS10", "DGS2",
                     "T10Y2Y", "DTWEXBGS", "UNRATE", "CPIAUCSL"]

        def _work():
            try:
                # ── 第一步: 读缓存/种子, 秒出界面 ──
                fred = {}       # {sid: DataFrame}
                need_fetch = [] # 需要网络拉取的 sid
                states = {}     # {sid: "fresh"/"stale"/"seed"}

                for sid in FRED_SIDS:
                    df, state = self._fed_cache_get(sid)
                    if df is not None:
                        fred[sid] = df  # 不管 fresh/stale/seed 都先塞进去显示!
                        states[sid] = state
                        if force or state != "fresh":
                            need_fetch.append(sid)  # 非新鲜的 → 后台刷新
                    else:
                        need_fetch.append(sid)

                # 状态条文本 (区分 种子值 vs 缓存)
                seed_count = sum(1 for s in states.values() if s == "seed")
                stale_count = sum(1 for s in states.values() if s == "stale")
                fresh_count = sum(1 for s in states.values() if s == "fresh")
                if seed_count > 0 and fresh_count == 0:
                    tag = "🌱 种子值"
                elif stale_count > 0:
                    tag = f"💾 缓存(过期{stale_count}个)"
                else:
                    tag = "💾 缓存(全新鲜)"
                fetch_msg = f"· 后台刷新 {len(need_fetch)}个..." if need_fetch else ""
                win.after(0, lambda t=tag, m=fetch_msg, f=len(need_fetch):
                    status.configure(text=f"{t}  {len(fred)}/{len(FRED_SIDS)} {m}"))

                # ── 第二步: 串行拉取 (稳, 避免 FRED/网络并发超时) ──
                fetched = 0
                for sid in need_fetch:
                    df = self._fetch_fred_csv(sid, use_cache=False, timeout=20)
                    if df is not None and len(df) > 0:
                        fred[sid] = df  # 成功 → 覆盖
                    # 失败则保留缓存 (fred[sid] 里已有)
                    fetched += 1

                win.after(0, lambda: status.configure(
                    text=f"✅ FRED: {len(fred)}/{len(FRED_SIDS)} · ⏳ 渲染..."))

                # 2. 最新值
                def _latest(sid):
                    v = fred.get(sid)
                    if v is None: return None
                    try: return v["value"].iloc[-1]
                    except Exception: return None

                effr = _latest("DFF")          # 有效联邦基金利率
                tar_upper = _latest("DFEDTARU") # 目标上限
                tar_lower = _latest("DFEDTARL") # 目标下限
                dgs10 = _latest("DGS10")        # 10Y美债
                dgs2 = _latest("DGS2")          # 2Y美债
                t10y2y = _latest("T10Y2Y")      # 10Y-2Y利差
                dxy = _latest("DTWEXBGS")       # 美元指数
                unemp = _latest("UNRATE")       # 失业率

                # CPI: FRED是指数(1982=100), 手动算YoY
                cpi_yoy = None
                if "CPIAUCSL" in fred and len(fred["CPIAUCSL"]) >= 13:
                    cpi_df = fred["CPIAUCSL"]
                    last_val = cpi_df["value"].iloc[-1]
                    # 找12个月前 (CPI是月度)
                    idx = max(0, len(cpi_df) - 13)
                    year_ago = cpi_df["value"].iloc[idx]
                    if year_ago > 0:
                        cpi_yoy = (last_val / year_ago - 1) * 100

                # 3. FOMC决策表
                fomc_df = self._get_fomc_data()

                # 4. 周期判断
                effr_df = fred.get("DFF")
                cycle = self._classify_fed_cycle(fomc_df, effr_df)

                # ── 主线程更新UI ──
                def _ui():
                    # 更新指标卡
                    if effr is not None:
                        _update_card(card_effr, effr, "%")
                    if tar_upper is not None and tar_lower is not None:
                        rng_txt = f"{tar_lower:.2f} - {tar_upper:.2f}"
                        _update_card(card_range, rng_txt, "%")
                    if t10y2y is not None:
                        _update_card(card_t10y2y, t10y2y, "%")
                        # 利差负数=倒挂, 危险
                        if t10y2y < 0:
                            for ch in card_t10y2y.winfo_children():
                                try:
                                    sz = ch.cget("font")[1] if isinstance(ch.cget("font"), tuple) else 0
                                    if sz >= 18: ch.configure(fg="#FF5252")
                                except: pass
                    if dxy is not None:
                        _update_card(card_dxy, dxy, "")
                    if cpi_yoy is not None:
                        _update_card(card_cpi, cpi_yoy, "%")
                    if unemp is not None:
                        _update_card(card_unemp, unemp, "%")

                    # 周期信号
                    cs = cycle.get("stage", "未知")
                    cc = cycle.get("color", "#78909C")
                    cd = cycle.get("desc", "")
                    cycle_header.configure(
                        text=f"🔔 当前周期: {cs}", fg=cc, bg=cc)
                    cycle_stat.configure(bg="#16213E",
                        text=f"本轮累计 {cycle.get('total_bp', 0):+d}bp  ·  "
                             f"{'加息' if cycle.get('direction')=='hike' else '降息'} "
                             f"{cycle.get('cycle_count', 0)}次  ·  "
                             f"周期起点: {cycle.get('cycle_start', '—')}  ·  "
                             f"结束: {cycle.get('cycle_end', '—')}\n"
                             f"📝 {cd}")

                    # FOMC 决策表 (只显示2020年后的, 按日期倒序)
                    for iid in tree.get_children(): tree.delete(iid)
                    recent = fomc_df[fomc_df["date"] >= "2020-01-01"].iloc[::-1]
                    for _, r in recent.iterrows():
                        act = r["action"]
                        if act == "hike":
                            tag = "hike"; fg = "#FF5252"
                        elif act == "cut":
                            tag = "cut"; fg = "#69F0AE"
                        else:
                            tag = "hold"; fg = "#CFD8DC"
                        tree.insert("", _tk.END, values=(
                            r["date"],
                            {"hike": "加息", "cut": "降息", "hold": "维持"}[act],
                            f"{r['bp']:+d}",
                            r["label"],
                        ), tags=(tag,))
                    tree.tag_configure("hike", foreground=fg, background="#3E2723")
                    tree.tag_configure("cut", foreground=fg, background="#1B5E20")
                    tree.tag_configure("hold", foreground=fg, background="#263238")

                    # 利率曲线文本 (最新值 + 近30日变化)
                    lines = ["📈 美债收益率曲线 (最新)",
                             "=" * 42]
                    for sid, name in [("DGS2", "2年期"), ("DGS10", "10年期")]:
                        if sid in fred and len(fred[sid]) > 30:
                            df = fred[sid]
                            last_v = df["value"].iloc[-1]
                            old_v = df["value"].iloc[-31] if len(df) >= 31 else df["value"].iloc[0]
                            chg = last_v - old_v
                            chg_str = f"+{chg:.2f}" if chg >= 0 else f"{chg:.2f}"
                            lines.append(f"  {name}: {last_v:.2f}%  (30日 {chg_str}bp)")
                    if t10y2y is not None:
                        tag = "⚠️ 倒挂!" if t10y2y < 0 else "✅ 正常"
                        lines.append(f"  10Y-2Y 利差: {t10y2y:.2f}%  {tag}")
                    if "DTWEXBGS" in fred and len(fred["DTWEXBGS"]) > 30:
                        df = fred["DTWEXBGS"]
                        last_v = df["value"].iloc[-1]
                        old_v = df["value"].iloc[-31] if len(df) >= 31 else df["value"].iloc[0]
                        chg = last_v - old_v
                        lines.append(f"  美元指数 DXY: {last_v:.2f}  (30日 {chg:+.2f})")
                    if cpi_yoy is not None:
                        lines.append(f"  美国CPI YoY: {cpi_yoy:.1f}%")
                    if unemp is not None:
                        lines.append(f"  美国失业率: {unemp:.1f}%")
                    lines.append("")

                    # 近期走势 (最近10次FOMC决策)
                    recent_m = fomc_df.tail(10)
                    lines.append("📋 最近10次FOMC决策:")
                    lines.append("-" * 42)
                    for _, r in recent_m.iterrows():
                        act_icon = {"hike": "🔺", "cut": "🔻", "hold": "➖"}[r["action"]]
                        lines.append(f"  {act_icon} {r['date']}  {r['label']}")
                    curve_text.configure(state=_tk.NORMAL)
                    curve_text.delete("1.0", _tk.END)
                    curve_text.insert("1.0", "\n".join(lines))
                    curve_text.configure(state=_tk.DISABLED)

                    # 对A股传导
                    trans_lines = self._gen_transmission_analysis(
                        t10y2y, dxy, cycle.get("stage", ""),
                        cycle.get("direction", "hike"), effr)
                    trans_text.configure(state=_tk.NORMAL)
                    trans_text.delete("1.0", _tk.END)
                    trans_text.insert("1.0", trans_lines)
                    trans_text.configure(state=_tk.DISABLED)

                    # 策略建议
                    strat_lines = self._gen_strategy_advice(
                        t10y2y, dxy, cycle.get("stage", ""),
                        cycle.get("direction", "hike"), effr,
                        tar_upper, dgs10)
                    strat_text.configure(state=_tk.NORMAL)
                    strat_text.delete("1.0", _tk.END)
                    strat_text.insert("1.0", strat_lines)
                    strat_text.configure(state=_tk.DISABLED)

                    # Tab4: 历史周期对照 & 美元潮汐 & 预测框架
                    hist_lines = self._gen_history_and_predict(
                        t10y2y, dxy, cycle.get("stage", ""),
                        cycle.get("direction", "hike"), effr)
                    hist_text.configure(state=_tk.NORMAL)
                    hist_text.delete("1.0", _tk.END)
                    hist_text.insert("1.0", hist_lines)
                    hist_text.configure(state=_tk.DISABLED)

                    status.configure(
                        text=f"✅ 加载完成 · "
                             f"EFFR={effr:.2f}% | 10Y={dgs10:.2f}% | "
                             f"利差={t10y2y:.2f}% | DXY={dxy:.2f} | CPI={cpi_yoy:.1f}%")

                win.after(0, _ui)
            except Exception as e:
                err = traceback.format_exc()
                print(f"[美联储分析] 加载异常:\n{err}")
                win.after(0, lambda: status.configure(
                    text=f"❌ 加载失败: {type(e).__name__}: {str(e)[:60]}"))
        threading.Thread(target=_work, daemon=True).start()

    refresh_btn.configure(command=lambda: _load_data(force=True))
    win.after(200, _load_data)

    return win

def _gen_transmission_analysis(self, t10y2y, dxy, stage, direction, effr):
    """根据当前利率环境生成对A股传导分析"""
    lines = ["🌏 美联储政策 → A股传导机制分析", "=" * 52, ""]

    # 1. 利率路径
    effr_v = effr if effr is not None else 3.8
    if effr_v >= 4.0:
        lines.append("📌 [利率高位区] EFFR ≥ 4%")
        lines.append("  • 全球无风险利率中枢上移 → A股高估值成长股杀估值")
        lines.append("  • 科技股(AI/半导体/光模块)PE 30x+ 面临重估压力")
        lines.append("  • 利率高位对DCF模型影响最大的是长周期成长股")
    elif effr_v >= 3.0:
        lines.append("📌 [利率中高位区] 3% ≤ EFFR < 4%")
        lines.append("  • 全球流动性边际收紧，但不极端")
        lines.append("  • A股传导以结构性为主，而非系统性杀估值")
    else:
        lines.append("📌 [利率中低位区] EFFR < 3%")
        lines.append("  • 全球流动性宽松，成长股估值有支撑")

    # 2. 利差
    lines.append("")
    if t10y2y is not None:
        if t10y2y < 0:
            lines.append(f"📌 [利差倒挂] 10Y-2Y = {t10y2y:.2f}%")
            lines.append("  • 美债收益率曲线倒挂 = 市场定价衰退概率高")
            lines.append("  • 历史上倒挂后2-18个月美股/A股均有回调")
            lines.append("  • 此时配置防御类资产（公用事业、必选消费）")
        elif t10y2y < 0.5:
            lines.append(f"📌 [利差平坦] 10Y-2Y = {t10y2y:.2f}%")
            lines.append("  • 利差收窄，市场对未来增长预期悲观")
            lines.append("  • 关注长端利率是否继续上行（加息预期）")
        else:
            lines.append(f"📌 [利差正常] 10Y-2Y = {t10y2y:.2f}%")
            lines.append("  • 曲线陡峭，市场对未来增长有信心")

    # 3. 美元指数
    lines.append("")
    if dxy is not None:
        if dxy >= 115:
            lines.append(f"📌 [美元强势] DXY = {dxy:.1f}")
            lines.append("  • 强美元 → 资本从新兴市场回流美国")
            lines.append("  • 人民币面临贬值压力（但2026年实际在升值）")
            lines.append("  • 大宗商品以美元计价 → 油价/有色承压")
        elif dxy >= 105:
            lines.append(f"📌 [美元中性偏强] DXY = {dxy:.1f}")
            lines.append("  • 美元强势但不过分，对A股影响中等")
        else:
            lines.append(f"📌 [美元弱势] DXY = {dxy:.1f}")
            lines.append("  • 弱美元 → 资本回流新兴市场，利好A股外资流入")

    # 4. 周期位置
    lines.append("")
    lines.append(f"📌 [周期阶段] {stage}")
    if direction == "hike":
        lines.append("  • 加息周期整体偏空全球权益资产")
        lines.append("  • 但加息末期(最后1-2次)往往是利空出尽")
    else:
        lines.append("  • 降息周期整体利多全球权益资产")
        lines.append("  • 降息初期流动性改善最显著，利好高成长")

    # 5. 关键传导链条
    lines.append("")
    lines.append("🔗 关键传导链条:")
    lines.append("  美债10Y↑ → 全球无风险利率↑ → A股高PE杀估值")
    lines.append("  美联储加息 → 美元↑ → 人民币(若贬值) → 外资流出")
    lines.append("  美联储加息 → 大宗商品↓ → PPI↓ → A股周期股承压")
    lines.append("  美联储加息 → 美中利差扩大 → 中国央行降息空间受限")

    return "\n".join(lines)

def _gen_strategy_advice(self, t10y2y, dxy, stage, direction, effr, tar_upper, dgs10):
    """根据当前利率环境生成策略操作建议"""
    lines = ["🎯 策略操作建议", "=" * 52, ""]

    # 利率环境判定
    effr_v = effr if effr is not None else 3.8
    dgs10_v = dgs10 if dgs10 is not None else 4.5

    # ── 行业方向 ──
    lines.append("【行业配置方向】")
    lines.append("-" * 40)

    if effr_v >= 4.0 and direction == "hike":
        lines.append("✅ 利好: 银行/保险 (高利率环境净息差↑)")
        lines.append("✅ 利好: 电力/公用事业 (低估值防御属性)")
        lines.append("✅ 利好: 运营商 (高股息+防御)")
        lines.append("✅ 利好: 现金类资产/短债")
        lines.append("⚠️ 利空: AI/半导体/新能源 (杀高估值)")
        lines.append("⚠️ 利空: 航空/造纸 (美元强+油价高)")
        lines.append("⚠️ 利空: 成长风格整体")
    elif effr_v >= 3.0 and direction == "hike":
        lines.append("✅ 利好: 低估值蓝筹 (银行/运营商/煤炭)")
        lines.append("✅ 利好: 高股息 (红利指数)")
        lines.append("⚠️ 关注: 科技股是否出现业绩验证后的估值消化")
    elif direction == "cut":
        lines.append("✅ 利好: 成长风格整体 (科技/新能源/军工)")
        lines.append("✅ 利好: 小盘股 (降息+流动性改善)")
        lines.append("✅ 利好: 周期股 (大宗商品涨价+需求修复)")
        lines.append("⚠️ 注意: 银行净息差收窄")
    else:  # hold
        lines.append("✅ 利好: 均衡配置，结构性机会")
        lines.append("✅ 利好: 业绩确定性赛道")
        lines.append("⚠️ 关注: 政策面变化 (中美货币政策分化)")

    # 人民币受益行业 (用户对话里的关键点)
    lines.append("")
    lines.append("【人民币升值受益行业】")
    lines.append("-" * 40)
    lines.append("✅ 航空 (燃油成本+美元债偿付)")
    lines.append("✅ 造纸 (进口木浆以美元计价)")
    lines.append("✅ 进口依赖型企业 (原油/农产品进口)")
    lines.append("✅ 有美元债务的公司 (汇兑收益)")
    lines.append("⚠️ 出口链冲击有限 (60%贸易用人民币结算或已套保)")

    # ── 周期阶段对策 ──
    lines.append("")
    lines.append("【周期阶段对策】")
    lines.append("-" * 40)

    if "初期" in stage:
        lines.append("📌 加息/降息初期: 趋势刚开始")
        lines.append("  • 加息初期: 高位震荡为主，避免追高")
        lines.append("  • 降息初期: 可以逐步布局受益板块")
    elif "中期" in stage:
        lines.append("📌 周期中期: 趋势延续")
        lines.append("  • 加息中期: 防御为主，低估值配置")
        lines.append("  • 降息中期: 成长风格主导")
    elif "末期" in stage:
        lines.append("📌 加息末期: 最危险也最有机会的阶段")
        lines.append("  • 警惕'最后一加'后的市场恐慌 → 但往往是黄金坑")
        lines.append("  • 观察降息信号 (通胀明确回落+失业率上升)")
    elif "暂停" in stage:
        lines.append("📌 加息暂停期: 观望+结构性机会")
        lines.append("  • 美联储暂停但通胀仍高 → 不是转向，只是等待数据")
        lines.append("  • 关注每一次CPI/就业数据 → 决定是否重启加息")
    else:
        lines.append("📌 当前阶段: 观察为主，等待方向明确")

    # ── 关键观察指标 ──
    lines.append("")
    lines.append("【下周关键观察指标】")
    lines.append("-" * 40)
    lines.append(f"📊 美债10年期收益率: {dgs10_v:.2f}% (破5.2%是硬压力线)")
    if t10y2y is not None:
        lines.append(f"📊 10Y-2Y利差: {t10y2y:.2f}%")
    lines.append(f"📊 EFFR: {effr_v:.2f}% | 目标区间上限: "
                 f"{tar_upper:.2f}%" if tar_upper else f"📊 EFFR: {effr_v:.2f}%")
    lines.append("📅 下次FOMC会议: 2026-11-04 (Hold预期)")
    lines.append("📊 A股成交额能否重回2万亿 (市场温度计)")

    # ── 风险提示 ──
    lines.append("")
    lines.append("【风险提示】")
    lines.append("-" * 40)
    lines.append("⚠️ 美联储政策存在路径依赖和数据依赖，预测可能随时修正")
    lines.append("⚠️ 不要用'被收割'叙事做决策 — 它让你忽略自身估值和仓位")
    lines.append("⚠️ 真正有用的变量是利率、汇率、利差，不是阴谋论")
    lines.append("⚠️ 本模块仅提供框架参考，不构成投资建议")

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════
# 📚 历史周期对照 & 美元潮汐 & 预测框架 (硬编码知识库, 不依赖网络)
# ═══════════════════════════════════════════════════════════════════

# ── 历史危机模板 (5 次美元潮汐) ──
_FED_HISTORY = [
    {
        "period": "1982-1985 沃尔克强美元周期",
        "direction": "hike",
        "effr_range": "16% → 8% (高利率平台)",
        "trigger": "沃尔克反通胀革命 → 联邦基金利率冲到 16%",
        "dxy_peak": 164,
        "a_share": "A股 1983年才开市, 无对应",
        "impact": "拉美债务危机爆发 (1982), 墨西哥、阿根廷等国违约; 美日广场协议 (1985)",
        "takeaway": "强美元+高利率 = 新兴市场债务雪崩 + 大宗商品崩盘",
    },
    {
        "period": "1994-1995 格林斯潘隐形加息",
        "direction": "hike",
        "effr_range": "3% → 6% (7次加息)",
        "trigger": "通胀抬头 + 经济过热 → 连续加息, 每次 25bp",
        "dxy_peak": 101,
        "a_share": "A股1994年从1556跌到325 (-79%), 三大利空: 加息+扩容+国债",
        "impact": "墨西哥比索危机 (1994), 龙舌兰效应; 美债市场动荡",
        "takeaway": "隐形加息周期 = 新兴市场资本外流 + 全球股市先崩后稳",
    },
    {
        "period": "2004-2006 格林斯潘渐进加息",
        "direction": "hike",
        "effr_range": "1% → 5.25% (17次加息, 每次25bp)",
        "trigger": "互联网泡沫后复苏 → 货币政策回归正常",
        "dxy_peak": 88,
        "a_share": "A股998点历史大底 (2005.06) → 股改+大牛市起点",
        "impact": "美债收益率曲线倒挂 (2006), 随后次贷危机爆发 (2007-2008)",
        "takeaway": "渐进加息周期 = 长端利率滞后 → 收益率倒挂预警衰退",
    },
    {
        "period": "2015-2018 耶伦/鲍威尔加息 (缩表同步)",
        "direction": "hike",
        "effr_range": "0% → 2.5% (9次加息 + 缩表)",
        "trigger": "QE后复苏 → 首次正常化 + 缩表",
        "dxy_peak": 103,
        "a_share": "A股股灾(2015.06) → 熔断(2016.01) → 贸易战(2018), 全年-32%",
        "impact": "土耳其/阿根廷货币危机 (2018), 人民币汇率7.0 (2019.08)",
        "takeaway": "加息+缩表 = 双重紧缩 → 新兴市场压力最大, A股外资流出",
    },
    {
        "period": "2022-2023 鲍威尔史上最快加息",
        "direction": "hike",
        "effr_range": "0% → 5.5% (11次加息, 累计525bp)",
        "trigger": "疫情后40年高通胀 → 暴力加息",
        "dxy_peak": 114,
        "a_share": "A股4月27日疫情底 → 反弹 → 2022年全年-21%, 港股-34%",
        "impact": "英债危机/LDI爆炸 (2022.09); 硅谷银行倒闭/瑞信破产 (2023.03)",
        "takeaway": "暴力加息 = 金融机构先崩 (久期错配) → 风险资产普跌",
    },
]

# ── 美元潮汐规律 ──
_USD_TIDE = [
    ("潮汐", "规律", "对A股传导"),
    ("涨潮", "加息周期: 美债收益率↑, DXY↑", "A股高PE杀估值, 外资流出, 汇率承压"),
    ("退潮", "加息末期: 最后1-2次加息后停", "利空出尽, 恐慌砸出黄金坑, 逆向布局"),
    ("落潮", "降息周期: 美债收益率↓, DXY↓", "全球流动性宽松, 成长股+小盘占优"),
    ("蓄潮", "降息末期: 通胀回升 → 下一轮加息预期", "风格切换防御, 红利资产占优"),
]

# ── 当前周期预测框架 ──
_FED_PREDICT_CASES = {
    "当前": {
        "stage": "2026-09-16 启动加息 25bp (3.75-4.00%)",
        "effr": "4.00%",
        "dxy": "121.38",
        "t10y2y": "0.47%",
        "a_share": "节前避险+美债利率冲击, 深证9月-3.44%",
        "scenario": "历史最像 2018年 (鲍威尔首次任期加息+缩表同步)",
        "risk": "高 — 但不同处是 2026年中国已主动去杠杆+汇率稳+结售汇顺差",
    },
    "3个月": {
        "title": "2026 Q4 → 2027 Q1",
        "base_case": "加息25bp → 暂停 → 观察通胀数据 → 降息预期下修",
        "bull_case": "通胀快速回落(≤2.5%) → 2027Q1开始降息 → 成长股估值修复",
        "bear_case": "通胀粘性(≥3%) → 2027Q1再加息 → 全球再杀估值",
        "key_watch": "10月CPI(10/22), 11月FOMC(11/04), 12月FOMC(12/16)",
    },
    "1年": {
        "title": "2027年全年",
        "base_case": "加息暂停期 → 数据依赖 → 1-2次降息试探 → 回归中性利率(3%)",
        "historical_analog": "最像 2019年 (鲍威尔加息后暂停→降息)",
        "a_share_path": "若走2019路径: 2027H1震荡底 → H2成长股行情",
        "risk_factors": "特朗普政策扰动, 美债上限, 中国地产尾部风险",
    },
}

def _gen_history_and_predict(self, t10y2y, dxy, stage, direction, effr):
    """硬编码历史危机 + 美元潮汐 + 当前预测框架 — 全部不联网"""
    lines = ["📚 历史周期对照 & 美元潮汐 & 预测框架", "=" * 52, ""]

    # ── 1. 历史危机: 按当前周期阶段匹配 ──
    lines.append("━" * 42)
    lines.append("【一】美元潮汐 × 历史危机 (5 次)")
    lines.append("━" * 42)
    for h in self._FED_HISTORY:
        lines.append(f"\n📌 {h['period']}")
        lines.append(f"  周期: {h['direction']} | EFFR: {h['effr_range']} | DXY峰值: {h['dxy_peak']}")
        lines.append(f"  触发: {h['trigger']}")
        lines.append(f"  A股: {h['a_share']}")
        lines.append(f"  冲击: {h['impact']}")
        lines.append(f"  💡 启示: {h['takeaway']}")

    # ── 2. 美元潮汐规律 ──
    lines.append("\n")
    lines.append("━" * 42)
    lines.append("【二】美元潮汐四阶段")
    lines.append("━" * 42)
    for tide, rule, a_share in self._USD_TIDE[1:]:
        icon = "🔺" if tide == "涨潮" else "⚠️" if tide == "退潮" else "🔻" if tide == "落潮" else "⏸️"
        lines.append(f"  {icon} {tide}: {rule}")
        lines.append(f"     → {a_share}\n")

    # ── 3. 当前预测框架 ──
    lines.append("━" * 42)
    lines.append("【三】当前周期预测框架")
    lines.append("━" * 42)
    now = self._FED_PREDICT_CASES["当前"]
    lines.append(f"\n📍 当前状态 (2026-10)")
    lines.append(f"  {now['stage']}")
    lines.append(f"  EFFR={now['effr']} | DXY={now['dxy']} | 10Y-2Y={now['t10y2y']}")
    lines.append(f"  A股现状: {now['a_share']}")
    lines.append(f"  历史对照: {now['scenario']}")
    lines.append(f"  风险等级: {now['risk']}")

    q3 = self._FED_PREDICT_CASES["3个月"]
    lines.append(f"\n📅 3个月预测 ({q3['title']})")
    lines.append(f"  🟢 基准: {q3['base_case']}")
    lines.append(f"  🚀 乐观: {q3['bull_case']}")
    lines.append(f"  🛑 悲观: {q3['bear_case']}")
    lines.append(f"  🔑 关键观察: {q3['key_watch']}")

    y1 = self._FED_PREDICT_CASES["1年"]
    lines.append(f"\n📅 1年预测 ({y1['title']})")
    lines.append(f"  🟢 基准: {y1['base_case']}")
    lines.append(f"  历史对照: {y1['historical_analog']}")
    lines.append(f"  A股路径: {y1['a_share_path']}")
    lines.append(f"  ⚠️ 风险: {y1['risk_factors']}")

    # ── 4. 与当前实时数据结合的建议 ──
    lines.append("\n━" * 42)
    lines.append("【四】结合你当前看到的数据的判断】")
    lines.append("━" * 42)
    effr_v = effr if effr is not None else 4.0
    dxy_v = dxy if dxy is not None else 121
    t10y2y_v = t10y2y if t10y2y is not None else 0.47

    lines.append(f"\n  你当前的参数:")
    lines.append(f"    EFFR={effr_v:.2f}%  DXY={dxy_v:.1f}  10Y-2Y={t10y2y_v:.2f}%  周期={stage}")

    # 当前周期 → 最像哪段历史
    if direction == "hike":
        if effr_v >= 4.0 and "初期" in stage:
            analog = "2018年首次加息周期 (9次加息+缩表)"
            lines.append(f"\n  🔍 最像历史时期: {analog}")
            lines.append(f"     → 参考2018年A股表现: 上证指数-25%, 创业板-32%")
            lines.append(f"     → 但当前汇率稳+外资结售汇顺差, 跌幅应该温和")
        elif "末期" in stage or "暂停" in stage:
            analog = "2018年底加息暂停期 (鲍威尔180度转向)"
            lines.append(f"\n  🔍 最像历史时期: {analog}")
            lines.append(f"     → 参考2019年A股表现: 深证成指+43%, 创业板+48%")
            lines.append(f"     → 加息暂停后, 成长股通常反弹最快")
    else:
        analog = "2024年降息初期"
        lines.append(f"\n  🔍 最像历史时期: {analog}")

    if dxy_v >= 120:
        lines.append(f"\n  ⚠️ 美元指数 ≥ 120 — 强美元警戒")
        lines.append(f"     → 历史上 DXY≥120 时新兴市场压力最大 (2022年9月114已导致英债危机)")
        lines.append(f"     → 但 DXY 高 不一定 等于 A股崩 — 关键看 汇率 能否稳住 + 外资是否持续流入")
    if t10y2y_v < 0:
        lines.append(f"\n  ⚠️ 10Y-2Y 利差倒挂 — 衰退预警")
        lines.append(f"     → 历史规律: 倒挂后 2-18 个月美股/A股均有回调")
    elif t10y2y_v < 0.5:
        lines.append(f"\n  🔍 利差平坦化 — 市场在定价增长放缓")
        lines.append(f"     → 从 {t10y2y_v:.2f}% 看, 目前还正常, 但在收窄")

    lines.append(f"\n━" * 42)
    lines.append("【五】一个简化决策框架】")
    lines.append("━" * 42)
    lines.append("""
  看加息/降息周期, 然后看利差, 最后看汇率:
① 加息 + 利差负 = 防御 + 警惕衰退
② 加息 + 利差正 + DXY高 = 大盘价值/红利
③ 降息 + 利差负 = 成长反弹 + 小盘活跃
④ 降息 + 利差正 + DXY低 = 牛市环境
⑤ 汇率升值 + 结售汇顺差 = 外资不慌, A股有底
  
  当前你在: ② 附近
""")

    return "\n".join(lines)

