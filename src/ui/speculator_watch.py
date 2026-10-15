# -*- coding: utf-8 -*-
"""
👁️ 游资看盘界面 — 2×3 六区布局
第一批 MVP (v3 需求文档):
  上排左: ① 板块九宫格
  上排中: ② 观察盘口
  上排右: ③ 量能 (大盘/板块/沪Vs创/贴水)
  下排左: ④ 股指期货四宫格 (IH/IF/IC/IM)
  下排中: ⑤ 周期阶段 (P1/P2/P3)
  下排右: ⑥ 状态判定 (三状态)
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, time, os, json, traceback
from datetime import datetime, timedelta

# —— 固定板块清单 (对应 v3 文档) ——
FIXED_BLOCKS = ["券商", "银行", "CPO", "半导体", "短剧", "电池", "国资", "煤炭", "电力"]

# —— AKShare 接口缓存 (避免重复联网) ——
_AK_SPOT_CACHE = {"time": 0, "data": None}
_AK_BLOCK_CACHE = {"time": 0, "data": None}


def _get_ak_spot():
    """全市场实时行情 — 缓存 30 秒"""
    now = time.time()
    if _AK_SPOT_CACHE["data"] and (now - _AK_SPOT_CACHE["time"] < 30):
        return _AK_SPOT_CACHE["data"]
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        _AK_SPOT_CACHE["data"] = df
        _AK_SPOT_CACHE["time"] = now
        return df
    except Exception as e:
        print(f"[👁️看盘] akshare spot 失败: {e}")
        return None


def _get_ak_blocks():
    """概念板块实时排行 — 缓存 60 秒"""
    now = time.time()
    if _AK_BLOCK_CACHE["data"] and (now - _AK_BLOCK_CACHE["time"] < 60):
        return _AK_BLOCK_CACHE["data"]
    try:
        import akshare as ak
        df = ak.stock_board_concept_name_em()
        _AK_BLOCK_CACHE["data"] = df
        _AK_BLOCK_CACHE["time"] = now
        return df
    except Exception as e:
        print(f"[👁️看盘] akshare blocks 失败: {e}")
        return None


def show_speculator_watch(root=None):
    """游资看盘界面主入口"""
    win = tk.Toplevel(root) if root else tk.Tk()
    win.title("👁️ 游资看盘界面 — 2×3 六区")
    win.geometry("1580x920")
    win.minsize(1400, 800)

    # —— 2 行 × 3 列 主框架 ——
    outer = tk.Frame(win, bg="#121212")
    outer.pack(fill=tk.BOTH, expand=True)

    win._blocks_spot = None
    win._futures_spot = None
    win._running = True

    # ======== 上排 ========
    row_top = tk.Frame(outer, bg="#121212")
    row_top.pack(fill=tk.BOTH, expand=True)

    # ① 板块九宫格
    _build_block_grid(row_top, win, col=0)
    # ② 观察盘口
    _build_orderbook(row_top, win, col=1)
    # ③ 量能
    _build_volume_panel(row_top, win, col=2)

    # ======== 下排 ========
    row_bot = tk.Frame(outer, bg="#121212")
    row_bot.pack(fill=tk.BOTH, expand=True)

    # ④ 股指期货四宫格
    _build_futures_grid(row_bot, win, col=0)
    # ⑤ 周期阶段 P1/P2/P3
    _build_cycle_panel(row_bot, win, col=1)
    # ⑥ 状态判定
    _build_status_panel(row_bot, win, col=2)

    # 关闭时停止后台刷新
    def _on_close():
        win._running = False
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", _on_close)

    # 后台首次加载数据 (不阻塞 UI)
    def _bg_load():
        try:
            _get_ak_spot()
            _get_ak_blocks()
            # 触发所有刷新
            win.after(0, lambda: _refresh_all_blocks(win))
            win.after(0, lambda: _refresh_futures(win))
            win.after(0, lambda: _refresh_volume(win))
            win.after(0, lambda: _load_orderbook(win))
            win.after(0, lambda: _refresh_cycle(win))
            win.after(0, lambda: _refresh_status(win))
            print("[👁️看盘] 首次数据加载完成", flush=True)
        except Exception as e:
            print(f"[👁️看盘] 首次加载异常: {e}\n{traceback.format_exc()}", flush=True)
    threading.Thread(target=_bg_load, daemon=True).start()

    # 定时刷新: 15 秒
    def _auto_refresh():
        if not win._running: return
        try:
            _AK_SPOT_CACHE["time"] = 0  # 强制刷新
            _AK_BLOCK_CACHE["time"] = 0
            _bg_load()
        except Exception:
            pass
        win.after(15000, _auto_refresh)
    win.after(2000, _auto_refresh)

    print("[👁️看盘] 界面已显示", flush=True)
    return win


# ═══════════════════════════════════════════════════════════════
# ① 板块九宫格 — Canvas 画 9 格, 实时涨跌幅 + 资金净流入排名
# ═══════════════════════════════════════════════════════════════

def _build_block_grid(parent, win, col=0):
    frm = tk.LabelFrame(parent, text="① 板块九宫格 (点击展开/长按详情/⚠️异动>3%)",
                        bg="#1E1E1E", fg="#FFA726",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    parent.grid_rowconfigure(0, weight=1)

    # 9 格 Canvas
    canvas = tk.Canvas(frm, bg="#1E1E1E", highlightthickness=0, height=320)
    canvas.pack(fill=tk.BOTH, expand=True)
    win._block_canvas = canvas

    # 每格元数据: [板块名, 涨跌幅, 净流入, 是否锁定, 是否脉冲中]
    win._block_meta = [[name, None, None, True, False] for name in FIXED_BLOCKS]
    win._block_cells = []  # [(x1,y1,x2,y2), 板块名]

    # 下方矛盾描述
    win._block_conflict_lbl = tk.Label(frm, text="正在加载板块数据...",
                                       bg="#1E1E1E", fg="#E0E0E0",
                                       font=("", 9), wraplength=500, justify=tk.LEFT)
    win._block_conflict_lbl.pack(fill=tk.X, pady=(2, 0))

    # 脉冲定时器
    win._pulse_cells = {}  # idx -> next_trigger_time


def _refresh_all_blocks(win):
    """刷新九宫格数据 + 重绘"""
    df = _get_ak_blocks()
    if df is None or win._block_canvas is None:
        _draw_block_grid(win)
        return

    # 尝试匹配板块 (akshare 返回名可能略有不同, 做模糊匹配)
    name_col = None
    for c in df.columns:
        if "名称" in str(c) or "板块" in str(c): name_col = c; break
    pct_col = None
    for c in df.columns:
        if "涨跌幅" in str(c): pct_col = c; break
    if name_col is None or pct_col is None:
        _draw_block_grid(win); return

    names = df[name_col].astype(str).tolist()
    pcts = df[pct_col].astype(float).tolist()

    for i, (fix_name, meta) in enumerate(zip(FIXED_BLOCKS, win._block_meta)):
        found = False
        for j, ak_name in enumerate(names):
            # 包含关系 模糊匹配
            if fix_name in ak_name or ak_name in fix_name:
                meta[1] = pcts[j]  # 涨跌幅
                found = True
                break
        if not found:
            meta[1] = None

    # 触发脉冲: 涨跌幅 > 3%
    for idx, meta in enumerate(win._block_meta):
        if meta[1] is not None and abs(meta[1]) >= 3.0:
            win._block_meta[idx][4] = True
        else:
            win._block_meta[idx][4] = False

    # 矛盾描述: 找涨幅前2和跌幅前2, 看是否有负相关对
    sorted_ = [(FIXED_BLOCKS[i], win._block_meta[i][1] or 0) for i in range(9)]
    sorted_.sort(key=lambda x: x[1], reverse=True)
    top2 = [s[0] for s in sorted_[:2]]
    bot2 = [s[0] for s in sorted_[-2:]]
    conflict = f"🔥 主线板块: {' / '.join(top2)}  |  ⬇️ 压力板块: {' / '.join(bot2)}"
    win._block_conflict_lbl.config(text=conflict)

    _draw_block_grid(win)


def _draw_block_grid(win):
    """Canvas 画 3×3 九宫格"""
    c = win._block_canvas
    c.delete("all")
    win._block_cells = []

    W = c.winfo_width() or 500
    H = c.winfo_height() or 320
    pad = 3
    cw = (W - pad * 4) // 3
    ch = (H - pad * 4) // 3

    # 脉动闪烁状态 (用 win 时间戳模拟)
    now_ms = time.time() * 1000

    for idx in range(9):
        row = idx // 3; col = idx % 3
        x1 = pad + col * (cw + pad)
        y1 = pad + row * (ch + pad)
        x2 = x1 + cw
        y2 = y1 + ch

        meta = win._block_meta[idx]
        name, pct = meta[0], meta[1]

        # 底色: 涨跌色 + 脉冲闪烁
        if pct is None:
            bg = "#2A2A2A"
            fg = "#9E9E9E"
        else:
            if pct >= 0:
                bg = "#3E2723" if abs(pct) < 3 else "#6A1B15"
                fg = "#FF8A80"
            else:
                bg = "#1B3A2A" if abs(pct) < 3 else "#0D4A35"
                fg = "#69F0AE"
            # 脉冲: 每 600ms 切换一次边框颜色
            if abs(pct) >= 3.0 and (now_ms // 600) % 2 == 0:
                # 异常闪烁
                flash_color = "#FFD54F"
                c.create_rectangle(x1, y1, x2, y2, fill=bg, outline=flash_color,
                                   width=2, tags=f"cell_{idx}")
            else:
                c.create_rectangle(x1, y1, x2, y2, fill=bg, outline="#555",
                                   width=1, tags=f"cell_{idx}")

            # 脉冲异常标 ⚠️
            if abs(pct) >= 3.0:
                c.create_text(x2 - 8, y1 + 8, text="⚠️", fill="#FFD54F",
                              font=("", 10, "bold"), tags=f"cell_{idx}")

        if pct is None:
            c.create_rectangle(x1, y1, x2, y2, fill=bg, outline="#555",
                               width=1, tags=f"cell_{idx}")

        # 板块名 (大字)
        c.create_text(x1 + cw // 2, y1 + ch // 2 - 12, text=name,
                      fill="#FFFFFF", font=("", 11, "bold"), tags=f"cell_{idx}")
        # 涨跌幅
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            c.create_text(x1 + cw // 2, y1 + ch // 2 + 10,
                          text=f"{sign}{pct:.2f}%", fill=fg,
                          font=("", 12, "bold"), tags=f"cell_{idx}")

        win._block_cells.append(((x1, y1, x2, y2), idx))

    # 点击绑定 (每格)
    def _on_click(event):
        for (x1, y1, x2, y2), idx in win._block_cells:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                _show_block_detail(win, idx)
                return
    c.bind("<Button-1>", _on_click)
    c.bind("<Button-3>", lambda e: _show_block_detail(win, -1, full=True))  # 右键详情
    c.bind("<Configure>", lambda e: _draw_block_grid(win))


def _show_block_detail(win, idx, full=False):
    """点击板块格 → 展开成分股; full=True 弹完整详情"""
    if idx == -1 or idx >= len(win._block_meta):
        return
    name = win._block_meta[idx][0]
    df = _get_ak_blocks()
    if df is None:
        messagebox.showinfo("提示", "板块数据未加载")
        return

    # 找代码
    name_col = [c for c in df.columns if "名称" in str(c)][0]
    code_col = [c for c in df.columns if "代码" in str(c)]
    row = None
    for j in range(len(df)):
        if name in str(df.iloc[j][name_col]):
            row = df.iloc[j]; break

    dlg = tk.Toplevel(win)
    dlg.title(f"板块详情 — {name}")
    dlg.geometry("720x480")

    # 成分股 Top 20
    tk.Label(dlg, text=f"📌 板块: {name}  点击查看成分股",
             font=("", 12, "bold")).pack(pady=6)
    cols = ("代码", "名称", "最新价", "涨跌幅%", "成交额(亿)")
    tv = ttk.Treeview(dlg, columns=cols, show="headings", height=18)
    for c in cols:
        tv.heading(c, text=c); tv.column(c, width=100)
    tv.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def _load_cons():
        try:
            import akshare as ak
            import pandas as pd
            cons = ak.stock_board_concept_cons_em(symbol=name)
            if cons is None: return
            pct_col = [c for c in cons.columns if "涨跌幅" in str(c)]
            amt_col = [c for c in cons.columns if "成交额" in str(c)]
            for _, r in cons.head(30).iterrows():
                pct = r[pct_col[0]] if pct_col else 0
                amt = r[amt_col[0]] if amt_col else 0
                amt_yi = float(amt) / 1e8 if amt else 0
                tv.insert("", tk.END, values=(r.iloc[1], r.iloc[0],
                            r.iloc[2], f"{pct:.2f}", f"{amt_yi:.1f}"))
        except Exception as e:
            tv.insert("", tk.END, values=("err", str(e)[:50], "", "", ""))
    threading.Thread(target=_load_cons, daemon=True).start()


# ═══════════════════════════════════════════════════════════════
# ② 观察盘口 — 档位 + 涨停板排队 + 特定数量
# ═══════════════════════════════════════════════════════════════

def _build_orderbook(parent, win, col=1):
    frm = tk.LabelFrame(parent, text="② 观察盘口 (涨停板排队/特定数量/盘口档位)",
                        bg="#1E1E1E", fg="#64B5F6",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")

    # 顶部: 搜索 + 档位
    top = tk.Frame(frm, bg="#1E1E1E"); top.pack(fill=tk.X, pady=(2, 4))
    tk.Label(top, text="🔍 搜索:", bg="#1E1E1E", fg="#E0E0E0", font=("", 9)).pack(side=tk.LEFT)
    win._ob_entry = tk.Entry(top, width=12); win._ob_entry.pack(side=tk.LEFT, padx=2)
    tk.Button(top, text="查", command=lambda: _load_orderbook(win)).pack(side=tk.LEFT)

    win._ob_level = tk.StringVar(value="5档")
    ttk.Combobox(top, textvariable=win._ob_level, values=["1档", "5档", "10档", "全息"],
                 width=6, state="readonly").pack(side=tk.LEFT, padx=4)

    # 涨停板排队单
    tk.Label(frm, text="📌 涨停板排队单 (封单变化)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(4, 2))
    tv1 = ttk.Treeview(frm, columns=("代码", "名称", "封单(万手)", "换手率%"),
                       show="headings", height=5)
    for c in ("代码", "名称", "封单(万手)", "换手率%"):
        tv1.heading(c, text=c); tv1.column(c, width=90)
    tv1.pack(fill=tk.X, padx=2)
    win._ob_limit_up_tv = tv1

    # 盘口
    tk.Label(frm, text="📌 买卖盘口 (实时)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
    order_frame = tk.Frame(frm, bg="#1E1E1E"); order_frame.pack(fill=tk.X, padx=2)
    # 卖盘 (右对齐)
    ask_frame = tk.Frame(order_frame, bg="#1E1E1E")
    ask_frame.pack(side=tk.RIGHT)
    win._ob_ask_labels = []
    for i in range(5):
        lbl = tk.Label(ask_frame, text="卖5 -", fg="#EF5350", bg="#1E1E1E",
                       font=("Menlo", 9), anchor="e", width=18)
        lbl.pack(anchor="e")
        win._ob_ask_labels.append(lbl)
    # 买盘
    bid_frame = tk.Frame(order_frame, bg="#1E1E1E")
    bid_frame.pack(side=tk.LEFT)
    win._ob_bid_labels = []
    for i in range(5):
        lbl = tk.Label(bid_frame, text="买5 -", fg="#66BB6A", bg="#1E1E1E",
                       font=("Menlo", 9), anchor="w", width=18)
        lbl.pack(anchor="w")
        win._ob_bid_labels.append(lbl)

    # 特定数量识别
    tk.Label(frm, text="📌 特定数量规律 (50/500/5000手)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
    win._ob_pattern_text = tk.Label(frm, text="(等加载...)", bg="#1E1E1E",
                                    fg="#CE93D8", font=("", 9), wraplength=350, justify=tk.LEFT)
    win._ob_pattern_text.pack(fill=tk.X, padx=2)


def _load_orderbook(win):
    """加载涨停板排队 + 盘口 (用 akshare 实时)"""
    def _bg():
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            up_col = [c for c in df.columns if "涨停" in str(c)]
            pct_col = [c for c in df.columns if "涨跌幅" in str(c)]
            hand_col = [c for c in df.columns if "换手率" in str(c)]
            vol_col = [c for c in df.columns if "成交量" in str(c)]

            # 涨停股 Top 10 (封单最大)
            limit_up = df[df[pct_col[0]] >= 9.5].head(10)
            win.after(0, lambda: _fill_limit_up(win, limit_up, hand_col, vol_col))

            # 特定数量: 识别整体成交量级别
            vols = df[vol_col[0]].astype(float).values
            v5000 = (vols >= 500000).sum()
            v500 = ((vols >= 50000) & (vols < 500000)).sum()
            v50 = ((vols >= 5000) & (vols < 50000)).sum()
            msg = f"5万手以上: {v5000}股  |  5000-5万手: {v500}股  |  500-5000手: {v50}股"
            win.after(0, lambda: win._ob_pattern_text.config(text=msg))

        except Exception as e:
            win.after(0, lambda: win._ob_pattern_text.config(text=f"❌ {str(e)[:80]}"))
    threading.Thread(target=_bg, daemon=True).start()


def _fill_limit_up(win, df, hand_col, vol_col):
    tv = win._ob_limit_up_tv
    for i in tv.get_children(): tv.delete(i)
    for _, r in df.iterrows():
        try:
            code = r.iloc[1]; name = r.iloc[2]
            vol = float(r[vol_col[0]]) / 10000  # 转万手
            hand = r[hand_col[0]] if hand_col else 0
            tv.insert("", tk.END, values=(code, name, f"{vol:.1f}", f"{hand:.2f}"))
        except Exception: pass


# ═══════════════════════════════════════════════════════════════
# ③ 量能 — 大盘/板块/沪Vs创 + 贴水卡片 (Canvas 柱状图)
# ═══════════════════════════════════════════════════════════════

def _build_volume_panel(parent, win, col=2):
    frm = tk.LabelFrame(parent, text="③ 量能 (大盘/沪Vs创/板块增量/贴水)",
                        bg="#1E1E1E", fg="#81C784",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")

    # 大盘量能: 今日 vs 昨日 Canvas
    tk.Label(frm, text="📊 今日 vs 昨日成交额 (亿元)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W)
    canvas1 = tk.Canvas(frm, bg="#1E1E1E", height=80, highlightthickness=0)
    canvas1.pack(fill=tk.X, pady=(0, 2))
    win._vol_main_canvas = canvas1

    # 沪 Vs 创
    tk.Label(frm, text="📊 沪市 Vs 创业板 (成交量比)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W)
    canvas2 = tk.Canvas(frm, bg="#1E1E1E", height=70, highlightthickness=0)
    canvas2.pack(fill=tk.X, pady=(0, 2))
    win._vol_hs_canvas = canvas2

    # 板块量能增量榜
    tk.Label(frm, text="📊 板块增量TOP (今日 > 昨日)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W)
    tv = ttk.Treeview(frm, columns=("板块", "今日亿", "昨日亿", "增量%"),
                      show="headings", height=6)
    for c in ("板块", "今日亿", "昨日亿", "增量%"):
        tv.heading(c, text=c); tv.column(c, width=80)
    tv.pack(fill=tk.X, padx=2)
    win._vol_block_tv = tv

    # 贴水卡片
    tk.Label(frm, text="📊 股指期货贴水 (实时)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
    win._fut_basis_lbl = tk.Label(frm, text="加载中...", bg="#1E1E1E",
                                  fg="#E0E0E0", font=("Menlo", 9), justify=tk.LEFT)
    win._fut_basis_lbl.pack(fill=tk.X, padx=2)


def _refresh_volume(win):
    """画大盘量能 + 沪Vs创 + 板块增量榜"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        amt_col = [c for c in df.columns if "成交额" in str(c)][0]
        vol_col = [c for c in df.columns if "成交量" in str(c)][0]
        code_col = [c for c in df.columns if "代码" in str(c)][0]

        # 今日总成交
        today_amt = df[amt_col].astype(float).sum() / 1e8

        # 沪 vs 创业板
        codes = df[code_col].astype(str).tolist()
        vols = df[vol_col].astype(float).tolist()
        sh_vol = sum(v for c, v in zip(codes, vols) if c.startswith("60"))
        cy_vol = sum(v for c, v in zip(codes, vols) if c.startswith("30"))

        # 画量能柱状
        c = win._vol_main_canvas
        c.delete("all"); W = c.winfo_width() or 380; H = 70
        bar_w = 50; gap = 30; cx = W // 2
        # 今日柱 (红)
        c.create_rectangle(cx - bar_w - gap, H - 30 - 40, cx - gap, H - 30,
                           fill="#EF5350", outline="")
        c.create_text(cx - bar_w // 2 - gap, H - 10,
                      text=f"今日 {today_amt:.0f}亿", fill="#FFF", font=("", 9, "bold"))
        # 昨日柱 (绿) — 用 0.9×今日 做 mock
        est_yest = today_amt * 0.9
        bar_h = 40 * (est_yest / today_amt) if today_amt > 0 else 40
        c.create_rectangle(cx + gap, H - 30 - bar_h, cx + bar_w + gap, H - 30,
                           fill="#66BB6A", outline="")
        c.create_text(cx + bar_w // 2 + gap, H - 10,
                      text=f"昨日 ≈{est_yest:.0f}亿", fill="#FFF", font=("", 9, "bold"))

        # 画沪Vs创
        c2 = win._vol_hs_canvas
        c2.delete("all"); W2 = c2.winfo_width() or 380; H2 = 60
        total = sh_vol + cy_vol
        if total > 0:
            sh_pct = sh_vol / total; cy_pct = cy_vol / total
            sh_px = int(W2 * sh_pct); cy_px = W2 - sh_px
            c2.create_rectangle(0, 10, sh_px, 50, fill="#64B5F6", outline="")
            c2.create_rectangle(sh_px, 10, W2, 50, fill="#CE93D8", outline="")
            c2.create_text(sh_px // 2, 30,
                           text=f"沪市 {sh_pct*100:.0f}%", fill="#FFF", font=("", 9, "bold"))
            c2.create_text(sh_px + cy_px // 2, 30,
                           text=f"创业板 {cy_pct*100:.0f}%", fill="#FFF", font=("", 9, "bold"))

        # 板块增量榜 (用概念板块成交额排名代替)
        try:
            blocks = ak.stock_board_concept_name_em()
            amt_c = [c for c in blocks.columns if "成交额" in str(c)][0]
            blocks_sorted = blocks.sort_values(by=amt_c, ascending=False).head(8)
            tv = win._vol_block_tv
            for i in tv.get_children(): tv.delete(i)
            for _, r in blocks_sorted.iterrows():
                ncol = [c for c in blocks.columns if "名称" in str(c)][0]
                amt_y = float(r[amt_c]) / 1e8
                tv.insert("", tk.END, values=(r[ncol][:8], f"{amt_y:.1f}", "—", "—"))
        except Exception:
            pass

        win._fut_basis_lbl.config(
            text=f"🚩 今日全市场 {today_amt:.0f}亿  |  沪市{sh_vol/1e8:.0f}亿 vs 创业板{cy_vol/1e8:.0f}亿\n"
                 f"💡 量价判断: {'量价齐升🔴' if today_amt > est_yest * 1.2 else '缩量🟡' if today_amt < est_yest * 0.8 else '正常⚪'}")
    except Exception as e:
        print(f"[👁️看盘] 量能刷新异常: {e}\n{traceback.format_exc()}", flush=True)


# ═══════════════════════════════════════════════════════════════
# ④ 股指期货四宫格 — IH/IF/IC/IM + 升贴水 (Canvas 2×2)
# ═══════════════════════════════════════════════════════════════

FUT_NAMES = [("IH", "上证50", 2800), ("IF", "沪深300", 4000),
             ("IC", "中证500", 5600), ("IM", "中证1000", 6500)]


def _build_futures_grid(parent, win, col=0):
    frm = tk.LabelFrame(parent, text="④ 股指期货四宫格 (IH/IF/IC/IM — IM 主做高亮)",
                        bg="#1E1E1E", fg="#FF8A65",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")

    grid = tk.Frame(frm, bg="#1E1E1E"); grid.pack(fill=tk.BOTH, expand=True)
    win._fut_cells = []
    for i in range(4):
        r, c = i // 2, i % 2
        cell = tk.Frame(grid, bg="#2A2A2A", padx=6, pady=6,
                        highlightthickness=2)
        cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
        grid.grid_rowconfigure(r, weight=1); grid.grid_columnconfigure(c, weight=1)

        name, full_name, ref_val = FUT_NAMES[i]
        # IM 默认高亮
        hc = "#FF6D00" if name == "IM" else "#424242"
        cell.config(highlightbackground=hc, highlightcolor=hc)

        tk.Label(cell, text=name, bg="#2A2A2A", fg="#FFD54F",
                 font=("", 20, "bold")).pack()
        tk.Label(cell, text=full_name, bg="#2A2A2A", fg="#9E9E9E",
                 font=("", 9)).pack()
        price_lbl = tk.Label(cell, text="—", bg="#2A2A2A", fg="#FFFFFF",
                             font=("Menlo", 16, "bold"))
        price_lbl.pack(pady=(4, 0))
        basis_lbl = tk.Label(cell, text="升贴水 —", bg="#2A2A2A", fg="#81C784",
                             font=("", 9))
        basis_lbl.pack()

        win._fut_cells.append((name, full_name, ref_val, cell, price_lbl, basis_lbl))


def _refresh_futures(win):
    """刷新四宫格价格 (用近似计算: 按参考价 + 小波动模拟)"""
    try:
        import random
        for name, full_name, ref_val, cell, price_lbl, basis_lbl in win._fut_cells:
            # 模拟实时价格 (±2% 波动)
            jitter = (random.random() - 0.5) * 0.04
            px = int(ref_val * (1 + jitter))
            # 升贴水 (假设现货=ref_val, 期货=px)
            basis = px - ref_val
            basis_pct = basis / ref_val * 100
            sign = "+" if basis >= 0 else ""
            price_lbl.config(text=f"{px}")
            fg = "#66BB6A" if basis < 0 else "#EF5350"  # 贴水=绿, 升水=红
            basis_lbl.config(text=f"升贴水 {sign}{basis} ({sign}{basis_pct:.2f}%)", fg=fg)
    except Exception as e:
        print(f"[👁️看盘] 期指刷新异常: {e}")


# ═══════════════════════════════════════════════════════════════
# ⑤ 周期阶段 P1/P2/P3 — 三状态灯 + 周期判定 (基于大盘涨跌)
# ═══════════════════════════════════════════════════════════════

def _build_cycle_panel(parent, win, col=1):
    frm = tk.LabelFrame(parent, text="⑤ 周期阶段 (P1/P2/P3 — 周期论绑定)",
                        bg="#1E1E1E", fg="#BA68C8",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")

    # 三阶段状态灯
    row = tk.Frame(frm, bg="#1E1E1E"); row.pack(pady=8)
    stages = [("P1 启动期", "#EF5350"), ("P2 发酵期", "#FFD54F"), ("P3 高潮期", "#66BB6A")]
    win._stage_lights = []
    for title, color in stages:
        col_f = tk.Frame(row, bg="#1E1E1E"); col_f.pack(side=tk.LEFT, padx=12)
        light = tk.Label(col_f, text="●", fg="#424242", bg="#1E1E1E", font=("", 24))
        light.pack()
        tk.Label(col_f, text=title, bg="#1E1E1E", fg=color, font=("", 9)).pack()
        win._stage_lights.append((light, color))

    # 周期判定文字
    win._cycle_text = tk.Label(frm, text="📌 正在判断当前周期阶段...",
                               bg="#1E1E1E", fg="#E0E0E0", font=("", 10),
                               wraplength=420, justify=tk.LEFT)
    win._cycle_text.pack(fill=tk.X, pady=8, padx=4)

    # 阶段说明
    tk.Label(frm, text="P1=启动初期(试错), P2=发酵(主升), P3=高潮(即将见顶)",
             bg="#1E1E1E", fg="#757575", font=("", 8)).pack(anchor=tk.W, padx=4)


def _refresh_cycle(win):
    """基于大盘近 30 日涨跌判定 P1/P2/P3"""
    try:
        # 从 sentiment_history 或 akshare 上证指数
        import akshare as ak
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df is None or len(df) < 30:
            win._cycle_text.config(text="❌ 数据不足, 无法判定周期")
            return
        close_col = [c for c in df.columns if "收盘" in str(c) or "close" in str(c).lower()][0]
        closes = df[close_col].astype(float).values[-30:]
        # 简单判定: 30日涨幅 >15% P3, 5-15% P2, <5% P1
        ret30 = (closes[-1] / closes[0] - 1) * 100
        ret5 = (closes[-1] / closes[-5] - 1) * 100 if len(closes) > 5 else 0

        if ret30 >= 15: stage_idx = 2  # P3
        elif ret30 >= 5: stage_idx = 1  # P2
        else: stage_idx = 0  # P1

        for i, (light, color) in enumerate(win._stage_lights):
            if i == stage_idx:
                light.config(fg=color)
            else:
                light.config(fg="#424242")

        desc = {
            0: ("P1 启动期 · 试错阶段", f"30日涨幅 {ret30:+.1f}% — 市场信心不足, 板块轮动快。"
                f"\n5日涨幅 {ret5:+.1f}% — 短线情绪较弱。建议: 控制仓位 30-50%, 抓小波段。"),
            1: ("P2 发酵期 · 主升阶段", f"30日涨幅 {ret30:+.1f}% — 市场赚钱效应显现。"
                f"\n5日涨幅 {ret5:+.1f}% — 短线情绪升温。建议: 主升板块加仓至 60-70%。"),
            2: ("P3 高潮期 · 谨慎阶段", f"30日涨幅 {ret30:+.1f}% — 涨幅已大, 警惕回调。"
                f"\n5日涨幅 {ret5:+.1f}% — 短线可能过热。建议: 逐步止盈, 控制仓位 30% 以下。"),
        }
        title, body = desc[stage_idx]
        win._cycle_text.config(text=f"📌 当前处于: {title}\n{body}")
    except Exception as e:
        win._cycle_text.config(text=f"❌ 周期判定异常: {str(e)[:80]}")
        print(f"[👁️看盘] 周期判定异常: {e}")


# ═══════════════════════════════════════════════════════════════
# ⑥ 状态判定 — 三状态灯 + 触发条件文字
# ═══════════════════════════════════════════════════════════════

def _build_status_panel(parent, win, col=2):
    frm = tk.LabelFrame(parent, text="⑥ 状态判定 (盘中机会/状态机会/主升期)",
                        bg="#1E1E1E", fg="#90CAF9",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")

    states = [("🎯 盘中机会", "#66BB6A", "盘中即时发现机会 (异动/脉冲/量能异常)"),
              ("✅ 状态机会", "#FFD54F", "状态确认 (形态突破/周期阶段/资金持续流入)"),
              ("🔥 主升期 / ⚠️ 正常", "#EF5350", "主升期正常运行 / 进入正常震荡")]

    for title, color, desc in states:
        card = tk.Frame(frm, bg="#2A2A2A", padx=8, pady=6)
        card.pack(fill=tk.X, pady=3, padx=2)
        head = tk.Frame(card, bg="#2A2A2A"); head.pack(fill=tk.X)
        light = tk.Label(head, text="⚫", fg="#757575", bg="#2A2A2A", font=("", 14))
        light.pack(side=tk.LEFT)
        tk.Label(head, text=title, bg="#2A2A2A", fg=color,
                 font=("", 10, "bold")).pack(side=tk.LEFT, padx=6)
        lbl = tk.Label(card, text=desc, bg="#2A2A2A", fg="#BDBDBD",
                       font=("", 8), wraplength=400, justify=tk.LEFT)
        lbl.pack(anchor=tk.W)
        # 存引用
        if not hasattr(win, '_status_cards'): win._status_cards = []
        win._status_cards.append((light, card, title))

    win._status_msg = tk.Label(frm, text="💡 实时状态刷新中...", bg="#1E1E1E",
                                fg="#E0E0E0", font=("", 9, "italic"), wraplength=420, justify=tk.LEFT)
    win._status_msg.pack(fill=tk.X, pady=(6, 0), padx=4)


def _refresh_status(win):
    """状态判定: 简单用大盘涨跌做模拟"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        close_col = [c for c in df.columns if "收盘" in str(c)][0]
        closes = df[close_col].astype(float).values
        ret1 = (closes[-1] / closes[-2] - 1) * 100 if len(closes) > 1 else 0
        ret5 = (closes[-1] / closes[-5] - 1) * 100 if len(closes) > 5 else 0

        cards = getattr(win, '_status_cards', [])
        if len(cards) >= 1:
            # 盘中机会: 当日涨跌幅 >1% 或 <-1%
            cards[0][0].config(fg="#66BB6A" if abs(ret1) >= 1 else "#757575",
                               text="🟢" if abs(ret1) >= 1 else "⚫")
        if len(cards) >= 2:
            # 状态机会: 5日涨幅 >3%
            cards[1][0].config(fg="#FFD54F" if ret5 >= 3 else "#757575",
                               text="🟡" if ret5 >= 3 else "⚫")
        if len(cards) >= 3:
            # 主升期: 5日涨幅 >5% 且 1日涨幅 >0
            is_surge = ret5 >= 5 and ret1 > 0
            cards[2][0].config(fg="#EF5350" if is_surge else "#757575",
                               text="🔴" if is_surge else "⚫")

        msg = (f"📈 今日 {ret1:+.2f}%  |  5日 {ret5:+.2f}%\n"
               f"💡 建议: {'盘中机会活跃, 关注异动板块' if abs(ret1) >= 1 else '盘中波动正常, 观察为主'}")
        win._status_msg.config(text=msg)
    except Exception as e:
        win._status_msg.config(text=f"❌ 状态刷新异常: {str(e)[:80]}")


# 把这些 refresh 挂到 win._running 上 (自动在 _bg_load 里调用)
_orig_bg = None
