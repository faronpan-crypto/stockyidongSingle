"""📊 TuShare 金融数据弹窗 Mixin

核心能力:
  TuShare Pro API (需要 TUSHARE_TOKEN):
    - 💰 每日指标 TOP (PE/PB/换手率/市值)
    - 🐉 龙虎榜每日明细
    - 👥 十大股东 / 十大流通股东
    - 📊 北向资金每日汇总
  AKShare fallback (免费公开, 没 TuShare 权限时自动用):
    - 🏒 涨停/跌停池
    - 📈 更多龙虎榜
"""
from __future__ import annotations

import os
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

try:
    import tushare as ts
    _TUSHARE_OK = True
    _TOKEN = os.getenv("TUSHARE_TOKEN", "")
    if _TOKEN:
        ts.set_token(_TOKEN)
except ImportError:
    _TUSHARE_OK = False

try:
    import akshare as ak
    _AK_OK = True
except ImportError:
    _AK_OK = False


class TushareMixin:
    """📊 TuShare 金融数据弹窗"""

    _TUSHARE_FEATURES = [
        ("💰 每日指标 TOP", "daily_basic"),
        ("🐉 龙虎榜明细", "top_list"),
        ("👥 十大股东", "top_holders"),
        ("👥 十大流通股东", "top_free_holders"),
        ("📊 北向资金汇总", "north_money"),
        ("🏒 涨停池 (公开)", "zt_pool"),
    ]

    # ═══════════════════════════════════════════════════════════
    # 🎯 主入口
    # ═══════════════════════════════════════════════════════════

    def _show_tushare_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("📊 TuShare · A股 / 财务 / 北向")
        dlg.geometry("1360x800")
        dlg.transient(self.root)

        topbar = ttk.Frame(dlg)
        topbar.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(topbar, text="📊 TuShare 金融数据", font=("", 13, "bold")).pack(side=tk.LEFT)
        self._tushare_status = tk.StringVar(
            value=f"就绪 · Token {'✅' if _TOKEN else '⚠️ 未配置'} · AKShare {'✅' if _AK_OK else '❌'}")
        ttk.Label(topbar, textvariable=self._tushare_status, foreground="gray").pack(side=tk.LEFT, padx=12)

        # PanedWindow
        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 左列
        left_frame = ttk.Frame(pw, width=210)
        pw.add(left_frame, weight=0)
        tk.Label(left_frame, text="🔍 功能", font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(4, 4))

        self._ts_feat_lb = tk.Listbox(left_frame, selectmode=tk.SINGLE, font=("", 11), height=9)
        for label, _ in self._TUSHARE_FEATURES:
            self._ts_feat_lb.insert(tk.END, label)
        self._ts_feat_lb.pack(fill=tk.X, padx=4)
        self._ts_feat_lb.bind("<<ListboxSelect>>", lambda e: self._ts_on_feat())

        # 输入区
        tk.Label(left_frame, text="📅 日期 (YYYYMMDD)", font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(10, 2))
        today = time.strftime("%Y%m%d")
        self._ts_date_var = tk.StringVar(value=today)
        ttk.Entry(left_frame, textvariable=self._ts_date_var, font=("", 10)).pack(fill=tk.X, padx=4)

        tk.Label(left_frame, text="🏷️ 股票代码 (6位)", font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(8, 2))
        self._ts_code_var = tk.StringVar(value="600519")
        ttk.Entry(left_frame, textvariable=self._ts_code_var, font=("", 10)).pack(fill=tk.X, padx=4)

        tk.Label(left_frame, text="📊 排序方式", font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(10, 2))
        self._ts_rank_var = tk.StringVar(value="pe_ttm")
        sort_frame = ttk.Frame(left_frame)
        sort_frame.pack(fill=tk.X, padx=4)
        for label, val in [("PE(TTM)", "pe_ttm"), ("换手率", "turnover_rate"), ("市值", "total_mv"), ("PB", "pb")]:
            ttk.Radiobutton(sort_frame, text=label, variable=self._ts_rank_var, value=val).pack(anchor="w")

        # 中列
        mid_frame = ttk.Frame(pw)
        pw.add(mid_frame, weight=3)

        search_frame = ttk.Frame(mid_frame)
        search_frame.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(search_frame, text="🚀 执行查询", command=self._ts_go, width=14)\
            .pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="📈 TOP50 指标", command=lambda: self._ts_do("daily_basic")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="🐉 龙虎榜", command=lambda: self._ts_do("top_list")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="🏒 涨停池", command=lambda: self._ts_do("zt_pool")).pack(side=tk.LEFT, padx=2)

        self._ts_tree_frame = ttk.Frame(mid_frame)
        self._ts_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 右列
        right_frame = ttk.Frame(pw, width=420)
        pw.add(right_frame, weight=2)
        ttk.Label(right_frame, text="📖 详情", font=("", 11, "bold")).pack(anchor="w", padx=6, pady=4)
        self._ts_detail_text = tk.Text(right_frame, wrap=tk.WORD, font=("TkDefaultFont", 10),
                                       background="#e3f2fd", height=30)
        self._ts_detail_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._ts_detail_text.configure(state=tk.DISABLED)

        # init
        dlg.after(150, lambda: (self._ts_feat_lb.selection_set(0), self._ts_do("daily_basic")))

    def _ts_on_feat(self):
        sel = self._ts_feat_lb.curselection()
        if not sel: return
        _, mode = self._TUSHARE_FEATURES[sel[0]]
        self._ts_do(mode)

    def _ts_go(self):
        sel = self._ts_feat_lb.curselection()
        if sel: self._ts_do(self._TUSHARE_FEATURES[sel[0]][1])

    def _ts_do(self, mode: str):
        self._ts_status.set(f"⏳ {mode}...")
        for w in self._ts_tree_frame.winfo_children(): w.destroy()

        # 先放一个 loading Label
        loading = ttk.Label(self._ts_tree_frame, text="⏳ 加载中...",
                            font=("", 14), foreground="gray")
        loading.pack(expand=True)
        self._ts_tree_frame.update()

        def _bg():
            t0 = time.time()
            r = self._ts_fetch(mode)
            dt = time.time() - t0
            self.root.after(0, lambda: self._ts_render(mode, r, dt))
        threading.Thread(target=_bg, daemon=True).start()

    def _ts_fetch(self, mode: str) -> dict:
        date = self._ts_date_var.get().strip() or time.strftime("%Y%m%d")
        code = self._ts_code_var.get().strip()
        ts_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ" if code[0] in "032" else code
        sort_col = self._ts_rank_var.get()

        # ── TuShare 接口 ──
        try:
            if _TOKEN and mode in ("daily_basic", "top_list", "top_holders", "top_free_holders", "north_money"):
                pro = ts.pro_api()

                if mode == "daily_basic":
                    df = pro.daily_basic(trade_date=date,
                        fields="ts_code,close,turnover_rate,turnover_rate_f,pe,pe_ttm,pb,ps,dv_ratio,total_mv,circ_mv")
                    if df is not None and sort_col in df.columns:
                        df = df.sort_values(sort_col, ascending=False).head(60)
                    return {"ok": True, "data": df, "date": date, "source": "TuShare"}

                elif mode == "top_list":
                    df = pro.top_list(trade_date=date)
                    return {"ok": True, "data": df, "date": date, "source": "TuShare"}

                elif mode == "top_holders":
                    df = pro.top10_holders(ts_code=ts_code, limit=10)
                    return {"ok": True, "data": df, "code": ts_code, "source": "TuShare"}

                elif mode == "top_free_holders":
                    df = pro.top10_floatholders(ts_code=ts_code, limit=10)
                    return {"ok": True, "data": df, "code": ts_code, "source": "TuShare"}

                elif mode == "north_money":
                    df = pro.moneyflow_hsgt(start_date=date, end_date=date)
                    return {"ok": True, "data": df, "date": date, "source": "TuShare"}

        except Exception as e:
            tu_error = str(e)[:200]
            # 如果是权限不足 → 继续尝试 akshare fallback
            if "权限" in tu_error or "没有接口" in tu_error:
                pass
            else:
                return {"ok": False, "error": f"TuShare 失败: {tu_error}"}

        # ── AKShare fallback ──
        try:
            if _AK_OK and mode == "zt_pool":
                import warnings; warnings.filterwarnings("ignore")
                df = ak.stock_zt_pool_em(date=date)
                return {"ok": True, "data": df, "date": date, "source": "AKShare(公开)"}
            elif _AK_OK and mode in ("daily_basic", "top_list", "north_money"):
                # 用 akshare 对应接口补
                import warnings; warnings.filterwarnings("ignore")
                if mode == "top_list":
                    df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
                    return {"ok": True, "data": df, "date": date, "source": "AKShare(公开)"}
                elif mode == "daily_basic":
                    # akshare 没有直接每日指标，返回 None 让 UI 提示
                    pass
                elif mode == "north_money":
                    df = ak.stock_hsgt_hist_em(symbol="北向资金")
                    if df is not None and not df.empty:
                        df = df.tail(30)
                        return {"ok": True, "data": df, "date": date, "source": "AKShare(公开)"}
        except Exception as e:
            ak_error = str(e)[:200]
            return {"ok": False, "error": f"TuShare+AKShare 都失败:\nTuShare: {tu_error[:80] if 'tu_error' in dir() else '未调'}\nAKShare: {ak_error}"}

        return {"ok": False, "error": f"⚠️ 接口 {mode} 当前无可用数据源\n\n💡 尝试:\n• 打开 TuShare 弹窗时确认 Token 已配置\n• 涨停池改用左列「🏒 涨停池(公开)」\n• 北向资金试试改日期"}

    def _ts_render(self, mode: str, r: dict, dt: float):
        # 清空 loading
        for w in self._ts_tree_frame.winfo_children(): w.destroy()

        src = r.get("source", "TuShare")

        if not r.get("ok"):
            # 在中间区域也显示错误!
            err_text = r.get("error", "未知错误")
            ttk.Label(self._ts_tree_frame, text="❌ 查询失败",
                      font=("", 14, "bold"), foreground="#c62828").pack(pady=(20, 6))
            ttk.Label(self._ts_tree_frame, text=err_text,
                      font=("", 10), foreground="#555", wraplength=500,
                      justify=tk.CENTER).pack(padx=20)
            self._ts_status.set(f"❌ 失败 ({dt:.1f}s)")
            self._ts_set_detail(f"❌ TuShare {mode}\n{'─'*40}\n\n{err_text}")
            return

        df = r.get("data")
        if df is None or (hasattr(df, "empty") and df.empty):
            ttk.Label(self._ts_tree_frame, text=f"⚠️ {mode} 无数据",
                      font=("", 14), foreground="#f57f17").pack(pady=30)
            ttk.Label(self._ts_tree_frame,
                      text=f"换个日期试试, 或检查股票代码\n数据源: {src}",
                      font=("", 10), foreground="gray").pack()
            self._ts_status.set(f"⚠️ 空 ({dt:.1f}s)")
            self._ts_set_detail(f"⚠️ 无数据\n\n{mode} 在 {r.get('date','')} 返回空\n数据源: {src}\n\n💡 非交易日属正常, 换个交易日试试")
            return

        headers = list(df.columns)[:10]
        tree = ttk.Treeview(self._ts_tree_frame, columns=headers, show="headings",
                            height=min(30, len(df)))
        for h in headers:
            tree.heading(h, text=str(h))
            w = 110 if h in ("ts_code", "holder_name", "name") else 80
            tree.column(h, width=w, anchor="center")

        # 涨停池红色高亮
        if mode == "zt_pool":
            for _, row in df.iterrows():
                pct = row.get("涨跌幅", row.get("pct_chg", 0))
                try:
                    tag = ("zt",) if float(pct) >= 9.5 else ()
                except Exception:
                    tag = ()
                tree.insert("", tk.END, values=[self._fmt(v) for v in row.values[:len(headers)]], tags=tag)
            tree.tag_configure("zt", background="#ffebee", foreground="#c62828")
        else:
            for _, row in df.iterrows():
                tree.insert("", tk.END, values=[self._fmt(v) for v in row.values[:len(headers)]])

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(self._ts_tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set); sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _sel(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            line = f"📊 TuShare {mode} ({src})\n{'─'*40}\n"
            for h in headers:
                line += f"  {h}: {df.iloc[idx][h]}\n"
            self._ts_set_detail(line)
        tree.bind("<<TreeviewSelect>>", _sel)

        def _dbl(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            row = df.iloc[idx]
            code = None
            for col in df.columns:
                if "代码" in str(col) or "code" in str(col).lower():
                    c = str(row[col])[:6]
                    if c and c[0].isdigit():
                        code = c; break
            if code:
                prefix = "sh" if code.startswith("6") else "sz"
                webbrowser.open(f"https://quote.eastmoney.com/{prefix}{code}.html")
        tree.bind("<Double-1>", _dbl)

        self._ts_status.set(f"✅ {mode}: {len(df)} 行 · {src} ({dt:.1f}s)")

    @staticmethod
    def _fmt(v):
        if v is None: return ""
        if hasattr(v, "item"): v = v.item()
        if isinstance(v, float): return f"{v:.2f}"
        return str(v)[:24]

    def _ts_set_detail(self, t: str):
        self._ts_detail_text.configure(state=tk.NORMAL)
        self._ts_detail_text.delete("1.0", tk.END)
        self._ts_detail_text.insert("1.0", t)
        self._ts_detail_text.configure(state=tk.DISABLED)
