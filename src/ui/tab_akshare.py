"""📈 AKShare 公开金融数据弹窗 Mixin

核心 akshare 公开接口:
  - 🏒 涨停/跌停池
  - 🐉 龙虎榜明细
  - 📊 CPI / PPI / GDP / PMI 宏观
  - 💰 中国国债收益率曲线
  - 📦 开放式基金排行
数据全部公开, 无需 Token
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
import webbrowser
from tkinter import ttk

try:
    import akshare as ak
    import warnings; warnings.filterwarnings("ignore")
    _HAS_AK = True
except ImportError:
    _HAS_AK = False


class AKShareMixin:
    """📈 AKShare 公开金融数据弹窗"""

    _AK_FEATURES = [
        ("🏒 涨停池", "zt_pool"),
        ("📉 跌停池", "dt_pool"),
        ("🐉 龙虎榜每日明细", "lhb_detail"),
        ("💰 国债收益率曲线", "bond_yield"),
        ("📊 CPI 同比", "cpi_year"),
        ("📊 PPI 同比", "ppi_year"),
        ("📊 GDP 同比", "gdp_year"),
        ("📊 PMI 官方", "pmi"),
        ("📦 开放式基金排行", "fund_open_rank"),
    ]

    def _show_akshare_dialog(self):
        if not _HAS_AK:
            tk.messagebox.showerror("依赖缺失", "pip install akshare")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("📈 AKShare · 公开金融数据")
        dlg.geometry("1380x820")
        dlg.transient(self.root)

        topbar = ttk.Frame(dlg)
        topbar.pack(fill=tk.X, padx=10, pady=(8, 2))
        tk.Label(topbar, text="📈 AKShare 公开金融数据", font=("", 13, "bold")).pack(side=tk.LEFT)
        self._ak_status = tk.StringVar(value=f"就绪 · akshare {ak.__version__} · 无需 Token")
        ttk.Label(topbar, textvariable=self._ak_status, foreground="gray").pack(side=tk.LEFT, padx=12)

        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 左列功能列表
        left = ttk.Frame(pw, width=210)
        pw.add(left, weight=0)
        tk.Label(left, text="🔍 功能", font=("", 11, "bold")).pack(anchor="w", padx=6, pady=4)
        self._ak_lb = tk.Listbox(left, selectmode=tk.SINGLE, font=("", 11), height=12)
        for label, _ in self._AK_FEATURES:
            self._ak_lb.insert(tk.END, label)
        self._ak_lb.pack(fill=tk.X, padx=4)
        self._ak_lb.bind("<<ListboxSelect>>", lambda e: self._ak_on_feat())

        # 日期/代码输入
        tk.Label(left, text="📅 日期 (YYYYMMDD)", font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(10, 2))
        today = time.strftime("%Y%m%d")
        self._ak_date_var = tk.StringVar(value=today)
        ttk.Entry(left, textvariable=self._ak_date_var, font=("", 10)).pack(fill=tk.X, padx=4)

        ttk.Button(left, text="🚀 执行 (Enter)", command=self._ak_go).pack(fill=tk.X, padx=4, pady=4)

        # 中列 Treeview
        mid = ttk.Frame(pw)
        pw.add(mid, weight=3)
        self._ak_tree_frame = ttk.Frame(mid)
        self._ak_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 右列详情
        right = ttk.Frame(pw, width=420)
        pw.add(right, weight=2)
        ttk.Label(right, text="📖 详情 / 说明", font=("", 11, "bold")).pack(anchor="w", padx=6, pady=4)
        self._ak_detail = tk.Text(right, wrap=tk.WORD, font=("TkDefaultFont", 10),
                                   background="#e8f5e9", height=30)
        self._ak_detail.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._ak_detail.configure(state=tk.DISABLED)

        dlg.bind("<Return>", lambda e: self._ak_go())

        # init 默认加载涨停池
        dlg.after(100, lambda: (self._ak_lb.selection_set(0), self._ak_do("zt_pool")))

    def _ak_on_feat(self):
        sel = self._ak_lb.curselection()
        if not sel: return
        self._ak_do(self._AK_FEATURES[sel[0]][1])

    def _ak_go(self):
        sel = self._ak_lb.curselection()
        if sel: self._ak_do(self._AK_FEATURES[sel[0]][1])

    def _ak_do(self, mode: str):
        self._ak_status.set(f"⏳ {mode}...")
        for w in self._ak_tree_frame.winfo_children(): w.destroy()

        def _bg():
            t0 = time.time()
            r = self._ak_fetch(mode)
            dt = time.time() - t0
            self.root.after(0, lambda: self._ak_render(mode, r, dt))
        threading.Thread(target=_bg, daemon=True).start()

    def _ak_fetch(self, mode: str) -> dict:
        date = self._ak_date_var.get().strip() or time.strftime("%Y%m%d")
        # YYYYMMDD → YYYY-MM-DD 一些接口需要
        date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else date
        date_slash = f"{date[:4]}/{date[4:6]}/{date[6:8]}" if len(date) == 8 else date
        try:
            if mode == "zt_pool":
                df = ak.stock_zt_pool_em(date=date)
            elif mode == "dt_pool":
                df = ak.stock_zt_pool_dtgc_em(date=date)
            elif mode == "lhb_detail":
                df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
            elif mode == "bond_yield":
                # 国债收益率曲线: 近 1 年
                from datetime import datetime, timedelta
                end = date_fmt
                start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
                start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
                df = ak.bond_china_yield(start_date=start_fmt, end_date=end)
            elif mode == "cpi_year":
                df = ak.macro_china_cpi()
            elif mode == "ppi_year":
                df = ak.macro_china_ppi()
            elif mode == "gdp_year":
                df = ak.macro_china_gdp()
            elif mode == "pmi":
                df = ak.macro_china_pmi()
            elif mode == "fund_open_rank":
                df = ak.fund_open_fund_rank_em(symbol="全部")
            else:
                return {"ok": False, "error": f"未知模式: {mode}"}
            return {"ok": True, "data": df}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}

    def _ak_render(self, mode: str, r: dict, dt: float):
        if not r.get("ok"):
            self._ak_status.set(f"❌ 失败 ({dt:.1f}s)")
            self._set_ak_detail(f"❌ {mode}\n\n{r.get('error','?')}\n\n💡 提示:\n• 东方财富接口可能需要换日期\n• 试试手动填 YYYYMMDD 格式\n• 非交易日涨停池为空属正常")
            return
        df = r.get("data")
        if df is None or df.empty:
            self._ak_status.set(f"⚠️ 无数据 ({dt:.1f}s)")
            self._set_ak_detail(f"⚠️ {mode} 返回空\n\n换个日期或检查 akshare 版本")
            return

        headers = list(df.columns)[:12]
        tree = ttk.Treeview(self._ak_tree_frame, columns=headers, show="headings",
                            height=min(30, len(df)))
        for h in headers:
            tree.heading(h, text=str(h))
            w = 100 if any(k in str(h) for k in ["名称", "代码", "holder", "名称"]) else 80
            tree.column(h, width=w, anchor="center")

        # 涨停池红色高亮, 跌停绿色
        highlight_map = {}
        if mode == "zt_pool":
            for idx, (_, row) in enumerate(df.iterrows()):
                c = row.get("pct_chg", row.get("涨跌幅", 0))
                tags = ("zt",) if c is not None and float(c) >= 9.5 else ()
                tree.insert("", tk.END, values=[self._fmt(v) for v in row.values[:len(headers)]], tags=tags)
            tree.tag_configure("zt", background="#ffebee", foreground="#c62828")
        elif mode == "dt_pool":
            for _, row in df.iterrows():
                tree.insert("", tk.END, values=[self._fmt(v) for v in row.values[:len(headers)]], tags=("dt",))
            tree.tag_configure("dt", background="#e8f5e9", foreground="#2e7d32")
        else:
            for _, row in df.iterrows():
                tree.insert("", tk.END, values=[self._fmt(v) for v in row.values[:len(headers)]])

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(self._ak_tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set); sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _sel(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            line = f"📈 AKShare {mode} 详情\n{'─'*40}\n"
            for h in headers:
                line += f"  {h}: {df.iloc[idx][h]}\n"
            self._set_ak_detail(line)
        tree.bind("<<TreeviewSelect>>", _sel)

        # 双击打开东方财富 (股票代码前加 sh/sz)
        def _dbl(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            row = df.iloc[idx]
            # 找代码列
            code = None
            for col in df.columns:
                if "代码" in str(col) or "code" in str(col).lower():
                    code = str(row[col])[:6]; break
            if code:
                prefix = "sh" if code.startswith("6") else "sz"
                webbrowser.open(f"https://quote.eastmoney.com/{prefix}{code}.html")
        tree.bind("<Double-1>", _dbl)

        self._ak_status.set(f"✅ {mode}: {len(df)} 行 ({dt:.1f}s)")
        self._set_ak_detail(f"📈 {mode} · {len(df)} 条\n\n💡 选中行 → 右列看详情\n💡 双击行 → 浏览器打开东方财富")

    @staticmethod
    def _fmt(v):
        if v is None: return ""
        if hasattr(v, "item"): v = v.item()  # numpy scalar
        if isinstance(v, float): return f"{v:.2f}"
        s = str(v)
        return s[:28]

    def _set_ak_detail(self, t: str):
        self._ak_detail.configure(state=tk.NORMAL)
        self._ak_detail.delete("1.0", tk.END)
        self._ak_detail.insert("1.0", t)
        try: self._apply_hyperlinks_to_text_widget(self._ak_detail)
        except Exception: pass
        self._ak_detail.configure(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════
    # 🎨 股票板块着色工具 (全局共用 Mixin)
    # ═══════════════════════════════════════════════════════════

    _STOCK_COLOR_MAP = [
        ("sh",   "#c62828", "沪市主板 (6xxxx)"),
        ("sz",   "#2e7d32", "深市主板 (00/01xxxx)"),
        ("gem",  "#1565c0", "创业板 (300xxx)"),
        ("kcb",  "#00695c", "科创板 (688xx)"),
        ("bj",   "#6a1b9a", "北交所 (8/4xxxx)"),
        ("hk",   "#ef6c00", "港股 (0xxxx.BO)"),
        ("fund", "#1976d2", "基金 (xxxxx.OF)"),
        ("etf",  "#7b1fa2", "ETF"),
    ]

    def _stock_color_tag(self, code: str) -> str:
        """根据股票代码返回板块 tag"""
        if not code: return "def"
        s = str(code).strip()
        c = s.split(".")[0]
        suffix = s.split(".")[-1].upper() if "." in s else ""
        if suffix == "SH":   return "kcb" if c.startswith("688") else "sh"
        if suffix == "SZ":   return "gem"  if c.startswith("300") else "sz"
        if suffix in ("BJ","BSE"): return "bj"
        if suffix in ("HK","BO"):  return "hk"
        if suffix == "OF":  return "fund"
        if c.startswith("688"): return "kcb"
        if c.startswith("6"):   return "sh"
        if c.startswith("3"):   return "gem"
        if c[0] in "01":  return "sz"
        if c[0] in "84":  return "bj"
        return "def"

    def _apply_stock_tag_config(self, tree, font=None):
        """给 Treeview 注册所有板块颜色 tag — 自动用 self.font_size"""
        fs = getattr(self, 'font_size', 16)
        ff = getattr(self, 'font_family', 'PingFang SC')
        default_font = font or (ff, fs, "bold")
        for tag, color, _ in self._STOCK_COLOR_MAP:
            try:
                tree.tag_configure(tag, foreground=color, font=default_font)
            except Exception:
                tree.tag_configure(tag, foreground=color)
        return tree

    def _stock_row_tags(self, code: str, extra=None) -> tuple:
        """Treeview insert 用 tags tuple"""
        base = (self._stock_color_tag(code),)
        if extra: base = base + (extra,)
        return base

    def _apply_ui_font(self, size=None, bg=None):
        """🎨 全局刷新所有 Treeview 的字号/背景色 — 动态调节控件调用"""
        try:
            if size is not None:
                self.font_size = max(10, min(24, int(size)))
            if bg is not None:
                self.tv_bg = bg
            fs = getattr(self, 'font_size', 16)
            ff = getattr(self, 'font_family', 'PingFang SC')
            rh = int(fs * 2.1)   # 行高约字号的 2.1 倍
            tv_font = (ff, fs, "bold")
            # 刷新全局 style
            _style = ttk.Style(self.root)
            _style.configure("Treeview", font=tv_font, rowheight=rh,
                background=self.tv_bg, fieldbackground=self.tv_bg)
            _style.configure("Treeview.Heading", font=(ff, fs, "bold"))
            self.root.option_add("*Treeview*RowHeight", rh)
            # 递归刷新所有已存在的 Treeview
            def _walk(w):
                try:
                    for child in w.winfo_children():
                        if isinstance(child, ttk.Treeview):
                            # 刷新全局字体 + 板块 tag 字体
                            try:
                                child.configure(font=tv_font, rowheight=rh)
                            except Exception:
                                pass
                            # 板块 tag 用新字号
                            self._apply_stock_tag_config(child)
                        _walk(child)
                except Exception:
                    pass
            _walk(self.root)
            return True
        except Exception as _e:
            print(f"[_apply_ui_font warn] {_e}", flush=True)
            return False
