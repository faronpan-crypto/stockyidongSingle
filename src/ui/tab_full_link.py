"""🔗 全链路个股分析弹窗 Mixin

一键查看一只股票的:
  - 📈 实时行情 (price/change/volume/turnover/pe/pb)
  - 💰 每日指标 (市值/换手率)
  - 📊 技术指标 (MA5/MA10/MA20/MA60)
  - 👥 十大股东
  - 🐉 龙虎榜 (近 N 日)
数据来源: tushare + akshare (组合)
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
    if os.getenv("TUSHARE_TOKEN"):
        ts.set_token(os.getenv("TUSHARE_TOKEN", ""))
        _HAS_TUSHARE = True
    else:
        _HAS_TUSHARE = False
except ImportError:
    _HAS_TUSHARE = False

try:
    import akshare as ak
    _HAS_AK = True
except ImportError:
    _HAS_AK = False


class FullLinkMixin:
    """🔗 全链路个股分析弹窗"""

    def _show_full_link_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🔗 全链路个股分析")
        dlg.geometry("1440x860")
        dlg.transient(self.root)

        # Top 搜索
        top = ttk.Frame(dlg)
        top.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(top, text="🔗 全链路个股分析", font=("", 14, "bold")).pack(side=tk.LEFT)
        self._fl_status = tk.StringVar(value=f"数据源: {'TuShare ✅' if _HAS_TUSHARE else ''} {'AKShare ✅' if _HAS_AK else ''}")
        ttk.Label(top, textvariable=self._fl_status, foreground="gray").pack(side=tk.LEFT, padx=14)

        ttk.Label(top, text="股票代码:", font=("", 11)).pack(side=tk.RIGHT, padx=(10, 2))
        self._fl_code_var = tk.StringVar(value="600519")
        ent = ttk.Entry(top, textvariable=self._fl_code_var, width=12, font=("", 11))
        ent.pack(side=tk.RIGHT)
        ttk.Button(top, text="🔍 一键分析", command=self._fl_analyze).pack(side=tk.RIGHT, padx=4)
        ent.bind("<Return>", lambda e: self._fl_analyze())

        # 快捷按钮
        quick = ttk.Frame(dlg)
        quick.pack(fill=tk.X, padx=10, pady=2)
        for code, name in [("600519", "贵州茅台"), ("000858", "五粮液"), ("300750", "宁德时代"),
                            ("002594", "比亚迪"), ("601318", "中国平安"), ("300059", "东方财富")]:
            tk.Button(quick, text=f"{name}", cursor="hand2", relief=tk.FLAT, fg="#1565C0",
                      font=("", 9), command=lambda c=code: (self._fl_code_var.set(c), self._fl_analyze())).pack(side=tk.LEFT, padx=3)

        # Notebook 多 Tab 展示
        self._fl_nb = ttk.Notebook(dlg)
        self._fl_nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._fl_tabs = {}
        for name in ["📊 核心指标", "💰 财务摘要", "👥 十大股东", "🐉 龙虎榜", "📈 K线技术"]:
            frame = ttk.Frame(self._fl_nb)
            self._fl_nb.add(frame, text=name)
            self._fl_tabs[name] = frame

        # init
        dlg.after(200, self._fl_analyze)

    def _fl_analyze(self):
        code = self._fl_code_var.get().strip()
        if not code or len(code) != 6:
            self._fl_status.set("⚠️ 请输入 6 位股票代码")
            return
        ts_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ" if code[0] in "032" else code
        self._fl_status.set(f"⏳ 分析 {code}...")
        self._fl_clear_tabs()

        def _bg():
            t0 = time.time()
            results = self._fl_collect(ts_code, code)
            dt = time.time() - t0
            self.root.after(0, lambda: self._fl_render_all(results, dt))
        threading.Thread(target=_bg, daemon=True).start()

    def _fl_clear_tabs(self):
        for name, frame in self._fl_tabs.items():
            for w in frame.winfo_children(): w.destroy()

    def _fl_collect(self, ts_code: str, code: str) -> dict:
        out = {}
        try:
            import tushare as ts
            pro = ts.pro_api()

            # 1. 核心指标 (daily_basic 最近交易日)
            from datetime import datetime, timedelta
            trade_date = datetime.now().strftime("%Y%m%d")
            for _ in range(5):  # 往前找最多 5 天
                try:
                    df = pro.daily_basic(ts_code=ts_code, trade_date=trade_date,
                        fields="ts_code,trade_date,close,turnover_rate,turnover_rate_f,pe,pe_ttm,pb,ps,dv_ratio,total_mv,circ_mv")
                    if df is not None and not df.empty:
                        out["core"] = df
                        break
                except Exception:
                    pass
                d = datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=1)
                trade_date = d.strftime("%Y%m%d")

            # 2. 日线行情 (近 120 天)
            end_dt = datetime.now().strftime("%Y%m%d")
            start_dt = (datetime.now() - timedelta(days=200)).strftime("%Y%m%d")
            try:
                df = pro.daily(ts_code=ts_code, start_date=start_dt, end_date=end_dt,
                               fields="ts_code,trade_date,open,high,low,close,vol,amount")
                if df is not None and not df.empty:
                    out["daily"] = df.sort_values("trade_date").tail(120)
            except Exception as e:
                out["daily_err"] = str(e)[:100]

            # 3. 十大股东 (最新报告期)
            try:
                df = pro.top10_holders(ts_code=ts_code, limit=10)
                if df is not None and not df.empty:
                    out["holders"] = df.nlargest(10, "hold_ratio")
            except Exception as e:
                out["holders_err"] = str(e)[:100]

            # 4. 龙虎榜 (近 15 天)
            try:
                df = pro.top_list(ts_code=ts_code, limit=15)
                if df is not None and not df.empty:
                    out["toplist"] = df
            except Exception as e:
                out["toplist_err"] = str(e)[:100]

        except Exception as e:
            out["err"] = str(e)[:200]

        return out

    def _fl_render_all(self, r: dict, dt: float):
        if "err" in r and not r:
            self._fl_status.set(f"❌ 失败: {r['err'][:40]}")
            return

        # Tab 1: 核心指标
        frame = self._fl_tabs["📊 核心指标"]
        core = r.get("core")
        if core is not None and not core.empty:
            row = core.iloc[0]
            grid = ttk.Frame(frame); grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            items = [
                ("代码", row.get("ts_code", "")),
                ("交易日", row.get("trade_date", "")),
                ("收盘价", f"{row.get('close', 0):.2f}"),
                ("换手率", f"{row.get('turnover_rate', 0):.2f}%"),
                ("换手率(自由)", f"{row.get('turnover_rate_f', 0):.2f}%"),
                ("PE(TTM)", f"{row.get('pe_ttm', 0):.2f}"),
                ("PB", f"{row.get('pb', 0):.2f}"),
                ("PS", f"{row.get('ps', 0):.2f}"),
                ("股息率", f"{row.get('dv_ratio', 0):.2f}%"),
                ("总市值(亿)", f"{row.get('total_mv', 0):.0f}"),
                ("流通市值(亿)", f"{row.get('circ_mv', 0):.0f}"),
            ]
            for i, (k, v) in enumerate(items):
                ttk.Label(grid, text=k, font=("", 10, "bold")).grid(row=i, column=0, sticky="w", padx=6, pady=4)
                ttk.Label(grid, text=str(v), font=("", 10)).grid(row=i, column=1, sticky="w", padx=6, pady=4)
            # 估值判断
            pe = row.get("pe_ttm", 0) or 0
            mv = row.get("total_mv", 0) or 0
            verdict = ttk.Label(grid, text=self._fl_valuation_hint(pe, mv), font=("", 10), foreground="#6a1b9a")
            verdict.grid(row=len(items), column=0, columnspan=2, sticky="w", padx=6, pady=10)
        else:
            ttk.Label(frame, text="⚠️ 暂无数据 (可能非交易日或 TuShare 权限不足)").pack(pady=30)

        # Tab 2: 财务摘要 (用日线做简易均线展示)
        frame2 = self._fl_tabs["💰 财务摘要"]
        self._fl_render_daily_summary(frame2, r.get("daily"))

        # Tab 3: 十大股东
        frame3 = self._fl_tabs["👥 十大股东"]
        self._fl_render_tree(frame3, r.get("holders"))

        # Tab 4: 龙虎榜
        frame4 = self._fl_tabs["🐉 龙虎榜"]
        self._fl_render_tree(frame4, r.get("toplist"))

        # Tab 5: K线技术
        frame5 = self._fl_tabs["📈 K线技术"]
        self._fl_render_ma_chart(frame5, r.get("daily"))

        self._fl_status.set(f"✅ 分析完成 ({dt:.1f}s)")

    def _fl_valuation_hint(self, pe, mv):
        if pe > 0 and pe < 15: h = f"PE={pe:.1f} 估值偏低 🟢"
        elif pe > 0 and pe < 30: h = f"PE={pe:.1f} 估值合理 🟡"
        elif pe > 0: h = f"PE={pe:.1f} 估值偏高 🔴"
        else: h = "PE 暂无"
        return f"💡 {h} | 总市值 {mv:.0f} 亿"

    def _fl_render_tree(self, frame, df):
        if df is None or df.empty:
            ttk.Label(frame, text="⚠️ 暂无数据").pack(pady=30); return
        headers = list(df.columns)[:8]
        tree = ttk.Treeview(frame, columns=headers, show="headings", height=20)
        for h in headers:
            tree.heading(h, text=h)
            tree.column(h, width=110, anchor="center")
        for _, row in df.iterrows():
            tree.insert("", tk.END, values=[str(row[h])[:24] if row[h] is not None else "" for h in headers])
        tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set); sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _fl_render_daily_summary(self, frame, df):
        # 用日线算涨跌幅 + 均线位置
        if df is None or df.empty:
            ttk.Label(frame, text="⚠️ 日线数据暂无 (TuShare 权限)").pack(pady=30); return
        df = df.sort_values("trade_date")
        closes = df["close"].values
        today = closes[-1]
        ma5 = closes[-5:].mean() if len(closes) >= 5 else today
        ma10 = closes[-10:].mean() if len(closes) >= 10 else today
        ma20 = closes[-20:].mean() if len(closes) >= 20 else today
        ma60 = closes[-60:].mean() if len(closes) >= 60 else today
        chg = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
        chg5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) >= 6 else 0
        chg20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) >= 21 else 0

        grid = ttk.Frame(frame); grid.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        data = [
            ("最新收盘价", f"{today:.2f}", "—"),
            ("日涨跌幅", f"{chg:+.2f}%", "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"),
            ("5日涨跌", f"{chg5:+.2f}%", "🟢" if chg5 > 0 else "🔴"),
            ("20日涨跌", f"{chg20:+.2f}%", "🟢" if chg20 > 0 else "🔴"),
            ("MA5", f"{ma5:.2f}", "站上" if today > ma5 else "跌破"),
            ("MA10", f"{ma10:.2f}", "站上" if today > ma10 else "跌破"),
            ("MA20", f"{ma20:.2f}", "站上" if today > ma20 else "跌破"),
            ("MA60", f"{ma60:.2f}", "站上" if today > ma60 else "跌破"),
            ("均线多头排列?", "✅" if today > ma5 > ma10 > ma20 > ma60 else "❌"),
        ]
        for i, (k, v, hint) in enumerate(data):
            ttk.Label(grid, text=k, font=("", 11, "bold")).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            ttk.Label(grid, text=v, font=("", 11)).grid(row=i, column=1, sticky="w", padx=8, pady=4)
            ttk.Label(grid, text=hint, font=("", 11)).grid(row=i, column=2, sticky="w", padx=8)

    def _fl_render_ma_chart(self, frame, df):
        if df is None or df.empty:
            ttk.Label(frame, text="⚠️ 暂无").pack(pady=30); return
        df = df.sort_values("trade_date").tail(120)
        closes = df["close"].values
        dates = df["trade_date"].values

        # 简易 ASCII 折线
        w, h = 60, 12
        lo, hi = closes.min(), closes.max()
        rng = hi - lo if hi != lo else 1
        grid = [[" " for _ in range(w)] for _ in range(h)]
        for x, c in enumerate(closes):
            y = int((1 - (c - lo) / rng) * (h - 1))
            grid[y][x % w] = "│"

        txt = tk.Text(frame, font=("Courier New", 9), wrap=tk.NONE, height=15)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        header = f"📈 收盘价走势 ({len(closes)} 日)  {dates[0]} → {dates[-1]}\n"
        header += f"  最低 {lo:.2f}  |  最高 {hi:.2f}  |  最新 {closes[-1]:.2f}\n\n"
        txt.insert("1.0", header + "\n".join("".join(row) for row in grid))

        # MA 对比
        ma5 = closes[-5:].mean()
        ma20 = closes[-20:].mean()
        latest = closes[-1]
        trend = "📈 上涨" if latest > ma5 > ma20 else "📉 下跌" if latest < ma5 < ma20 else "↔️ 震荡"
        txt.insert(tk.END, f"\n\n趋势判断: {trend} | MA5={ma5:.2f} MA20={ma20:.2f}")
        txt.configure(state=tk.DISABLED)
