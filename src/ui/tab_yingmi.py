"""盈米基金工具弹窗 Mixin

核心功能 (通过 akshare, 无需 token):
  - 🏆 开放式基金排行 (20677 只, 含近1周/1月/1年等收益率)
  - 🔍 基金名称搜索 (28252 只基金)
  - 👔 基金经理排行榜 (36711 条)
  - 🎯 盈米 10 大专业工作流浏览器快捷入口
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

try:
    import akshare as ak
except ImportError:
    ak = None


class YingmiMixin:
    """盈米基金研究 / 排行 / 筛选 弹窗"""

    # 🎯 盈米专业工作流 (浏览器打开)
    _YINGMI_WORKFLOWS = [
        ("📊 基金分析", "https://www.qieman.com/fund/analysis"),
        ("🔍 基金筛选", "https://www.qieman.com/fund/screener"),
        ("📈 策略分析", "https://www.qieman.com/strategy"),
        ("💼 组合诊断", "https://www.qieman.com/portfolio"),
        ("🌐 市场简报", "https://www.qieman.com/market"),
        ("🏠 家庭规划", "https://www.qieman.com/plan"),
        ("⚖️ 资产配置", "https://www.qieman.com/allocation"),
        ("📇 客户洞察", "https://www.qieman.com/client"),
        ("💬 产品沟通", "https://www.qieman.com/product"),
        ("✍️ 内容工作室", "https://www.qieman.com/content"),
    ]

    # 📋 排行排序选项
    _RANK_MODES = [
        ("近1周收益", "近1周"),
        ("近1月收益", "近1月"),
        ("近3月收益", "近3月"),
        ("近6月收益", "近6月"),
        ("近1年收益", "近1年"),
        ("近3年收益", "近3年"),
        ("今年以来", "今年来"),
        ("成立以来", "成立来"),
        ("日增长率", "日增长率"),
    ]

    # 🧠 快捷搜索模板
    _YINGMI_SEARCH_TEMPLATES = [
        "白酒",
        "半导体",
        "新能源",
        "医药",
        "消费",
        "宽基",
        "行业",
        "指数",
        "债券",
        "QDII",
    ]

    # ═══════════════════════════════════════════════════════════
    # 🎯 主入口: 盈米弹窗
    # ═══════════════════════════════════════════════════════════

    def _show_yingmi_dialog(self):
        """💎 盈米基金 弹窗 - 三列 PanedWindow"""
        if ak is None:
            tk.messagebox.showerror("依赖缺失",
                "需要安装 akshare: pip install akshare\n"
                "才能使用基金排行/搜索功能")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("💎 盈米基金 · 排行 / 筛选 / 盈米工作流")
        dlg.geometry("1400x820")
        dlg.transient(self.root)

        # ── 顶栏 ──
        topbar = ttk.Frame(dlg)
        topbar.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(topbar, text="💎 盈米基金研究助手",
                 font=("", 13, "bold")).pack(side=tk.LEFT)
        self._yingmi_status = tk.StringVar(value="就绪 · akshare 在线")
        ttk.Label(topbar, textvariable=self._yingmi_status,
                  foreground="gray").pack(side=tk.LEFT, padx=12)

        # ── 三列 PanedWindow ──
        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ═══ 左列: 功能入口 + 工作流 + 模板 ═══
        left_frame = ttk.Frame(pw, width=220)
        pw.add(left_frame, weight=0)

        tk.Label(left_frame, text="🔍 功能入口",
                 font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(4, 4))

        self._yingmi_feat_lb = tk.Listbox(left_frame, selectmode=tk.SINGLE,
                                           font=("", 11), activestyle="dotbox",
                                           height=6)
        self._yingmi_feat_lb.insert(tk.END, "🏆 开放式基金排行 TOP")
        self._yingmi_feat_lb.insert(tk.END, "🔎 基金名称/简称搜索")
        self._yingmi_feat_lb.insert(tk.END, "👔 基金经理排行榜")
        self._yingmi_feat_lb.pack(fill=tk.X, padx=4)
        self._yingmi_feat_lb.bind("<<ListboxSelect>>",
                                   lambda e: self._yingmi_on_feat_select())

        # 排序选项（在排行功能时显示）
        tk.Label(left_frame, text="📊 排序方式",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(8, 2))
        self._yingmi_rank_var = tk.StringVar(value="近1年收益")
        rank_frame = ttk.Frame(left_frame)
        rank_frame.pack(fill=tk.X, padx=4)
        for label, col in self._RANK_MODES[:5]:  # 只显示前5个
            ttk.Radiobutton(rank_frame, text=label, variable=self._yingmi_rank_var,
                            value=label).pack(anchor="w")

        # 快捷搜索模板
        tk.Label(left_frame, text="📋 搜索模板",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(8, 2))
        tpl_frame = ttk.Frame(left_frame)
        tpl_frame.pack(fill=tk.X, padx=4)
        for i, tpl in enumerate(self._YINGMI_SEARCH_TEMPLATES):
            btn = tk.Button(tpl_frame, text=tpl, cursor="hand2", relief=tk.FLAT,
                            fg="#2E7D32", font=("", 9), anchor="w", pady=1,
                            command=lambda tt=tpl: self._yingmi_preset_search(tt))
            btn.grid(row=i // 2, column=i % 2, sticky="w", padx=2, pady=1)

        # 盈米工作流分隔
        sep = ttk.Separator(left_frame, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, padx=6, pady=(10, 4))
        tk.Label(left_frame, text="🎯 盈米工作流",
                 font=("", 10, "bold")).pack(anchor="w", padx=6)
        for label, url in self._YINGMI_WORKFLOWS[:6]:
            btn = tk.Button(left_frame, text=label, cursor="hand2", relief=tk.FLAT,
                            fg="#6A1B9A", font=("", 9), anchor="w", pady=1,
                            command=lambda u=url: webbrowser.open_new_tab(u))
            btn.pack(anchor="w", padx=6)
        more_btn = tk.Button(left_frame, text="▸ 更多工作流 (10个)", cursor="hand2",
                              relief=tk.FLAT, fg="#6A1B9A", font=("", 9),
                              command=lambda: self._yingmi_show_more_flows())
        more_btn.pack(anchor="w", padx=6, pady=4)

        # ═══ 中列: 搜索框 + Notebook + 结果列表 ═══
        mid_frame = ttk.Frame(pw)
        pw.add(mid_frame, weight=3)

        # 搜索输入区
        search_frame = ttk.Frame(mid_frame)
        search_frame.pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(search_frame, text="🔎", font=("", 12)).pack(side=tk.LEFT)
        self._yingmi_query_ent = ttk.Entry(search_frame, font=("", 12))
        self._yingmi_query_ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._yingmi_query_ent.bind("<Return>",
                                     lambda e: self._yingmi_do_action("search"))

        ttk.Button(search_frame, text="🔎 搜索", width=8,
                    command=lambda: self._yingmi_do_action("search")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="🏆 排行 TOP50", width=12,
                    command=lambda: self._yingmi_do_action("rank")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="👔 经理榜", width=8,
                    command=lambda: self._yingmi_do_action("manager")).pack(side=tk.LEFT, padx=2)

        # Notebook
        self._yingmi_nb = ttk.Notebook(mid_frame)
        self._yingmi_nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        self._yingmi_list_tab = ttk.Frame(self._yingmi_nb)
        self._yingmi_nb.add(self._yingmi_list_tab, text="📋 结果列表")

        self._yingmi_rank_tab = ttk.Frame(self._yingmi_nb)
        self._yingmi_nb.add(self._yingmi_rank_tab, text="🏆 排行榜")

        # 列表容器
        self._yingmi_tree_frame = ttk.Frame(self._yingmi_list_tab)
        self._yingmi_tree_frame.pack(fill=tk.BOTH, expand=True)

        self._yingmi_rank_frame = ttk.Frame(self._yingmi_rank_tab)
        self._yingmi_rank_frame.pack(fill=tk.BOTH, expand=True)

        # ═══ 右列: Notebook (详情 + 重仓股) ═══
        right_frame = ttk.Frame(pw, width=460)
        pw.add(right_frame, weight=2)

        self._yingmi_right_nb = ttk.Notebook(right_frame)
        self._yingmi_right_nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Tab 1: 详情
        detail_tab = ttk.Frame(self._yingmi_right_nb)
        self._yingmi_right_nb.add(detail_tab, text="📖 详情说明")
        self._yingmi_detail_text = tk.Text(detail_tab, wrap=tk.WORD,
                                           font=("TkDefaultFont", 10),
                                           background="#fafafa", height=20)
        self._yingmi_detail_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._yingmi_detail_text.configure(state=tk.DISABLED)

        # Tab 2: 重仓股 (Treeview)
        hold_tab = ttk.Frame(self._yingmi_right_nb)
        self._yingmi_right_nb.add(hold_tab, text="📦 前十大重仓股")
        self._yingmi_hold_tree_frame = ttk.Frame(hold_tab)
        self._yingmi_hold_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        ttk.Label(hold_tab, text="💡 双击任意股票 → 弹出日K线图 (含MA/MACD/成交量)",
                  font=("", 9), foreground="gray").pack(anchor="w", padx=6, pady=(0, 2))

        # 初始化: 自动加载排行 TOP50
        dlg.after(100, lambda: (
            self._yingmi_feat_lb.selection_clear(0, tk.END),
            self._yingmi_feat_lb.selection_set(0),
            self._yingmi_do_action("rank")
        ))

    # ═══════════════════════════════════════════════════════════
    # 🎯 功能调度
    # ═══════════════════════════════════════════════════════════

    def _yingmi_on_feat_select(self):
        sel = self._yingmi_feat_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            self._yingmi_do_action("rank")
        elif idx == 1:
            q = self._yingmi_query_ent.get().strip()
            if q:
                self._yingmi_do_action("search")
            else:
                self._yingmi_status.set("⚠️ 请输入搜索关键词")
        elif idx == 2:
            self._yingmi_do_action("manager")

    def _yingmi_preset_search(self, tpl: str):
        self._yingmi_query_ent.delete(0, tk.END)
        self._yingmi_query_ent.insert(0, tpl)
        self._yingmi_do_action("search")

    def _yingmi_show_more_flows(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🎯 盈米 10 大专业工作流")
        dlg.geometry("520x480")
        dlg.transient(self.root)
        dlg.grab_set()

        text = tk.Text(dlg, wrap=tk.WORD, font=("", 10),
                        background="#f5f3ff")
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        text.insert("1.0", "💎 盈米 10 大专业工作流\n\n")
        text.insert(tk.END, "=" * 40 + "\n\n")
        for label, url in self._YINGMI_WORKFLOWS:
            text.insert(tk.END, f"{label}\n  🔗 {url}\n\n")
        text.configure(state=tk.DISABLED)

    def _yingmi_do_action(self, mode: str):
        """后台线程调 akshare"""
        # 清空
        for w in self._yingmi_tree_frame.winfo_children():
            w.destroy()
        for w in self._yingmi_rank_frame.winfo_children():
            w.destroy()
        self._yingmi_set_detail("⏳ 数据加载中...\n\nakshare 拉取基金数据, 请稍候...")

        if mode == "rank":
            sort_col = self._RANK_MODES[[l for l, _ in self._RANK_MODES].index(self._yingmi_rank_var())][1]
            self._yingmi_status.set(f"⏳ 拉取开放式基金排行, 按 {sort_col} 排序...")
            self._yingmi_nb.select(1)  # 切到排行 tab
        elif mode == "search":
            query = self._yingmi_query_ent.get().strip()
            if not query:
                self._yingmi_status.set("⚠️ 请输入关键词")
                self._yingmi_set_detail("⚠️ 请在搜索框输入基金简称或关键词\n\n"
                                         "示例: 白酒、半导体、新能源、宽基...")
                return
            self._yingmi_status.set(f"⏳ 搜索基金: {query}...")
            self._yingmi_nb.select(0)  # 切到列表 tab
        elif mode == "manager":
            self._yingmi_status.set("⏳ 拉取基金经理排行榜...")
            self._yingmi_nb.select(1)

        def _bg():
            t0 = time.time()
            result = {"ok": False, "mode": mode, "error": "", "data": None}
            try:
                if mode == "rank":
                    df = ak.fund_open_fund_rank_em()
                    sort_col = self._RANK_MODES[[l for l, _ in self._RANK_MODES].index(self._yingmi_rank_var())][1]
                    # 把 % 去掉排序
                    if sort_col in df.columns:
                        df[sort_col] = df[sort_col].astype(str).str.replace("%", "").str.replace("-", "0").astype(float, errors="ignore")
                    df_sorted = df.nlargest(80, sort_col) if sort_col in df.columns else df.head(80)
                    result["data"] = df_sorted.to_dict("records")
                elif mode == "search":
                    query = self._yingmi_query_ent.get().strip()
                    df = ak.fund_name_em()
                    mask = df["基金简称"].str.contains(query, na=False) | df["拼音全称"].str.contains(query, na=False)
                    matched = df[mask].head(100)
                    result["data"] = matched.to_dict("records")
                elif mode == "manager":
                    df = ak.fund_manager_em()
                    df["现任基金资产总规模_num"] = df["现任基金资产总规模"].astype(str).str.replace("万亿", "0000").str.replace("亿", "").astype(float, errors="ignore")
                    df_sorted = df.nlargest(50, "现任基金资产总规模_num")
                    result["data"] = df_sorted.to_dict("records")
                result["ok"] = True
            except Exception as e:
                result["error"] = str(e)
            dt = time.time() - t0
            self.root.after(0, lambda: self._yingmi_render_result(mode, result, dt))

        threading.Thread(target=_bg, daemon=True).start()

    # ═══════════════════════════════════════════════════════════
    # 🎨 渲染
    # ═══════════════════════════════════════════════════════════

    def _yingmi_render_result(self, mode: str, result: dict, dt: float):
        if not result.get("ok"):
            err = result.get("error", "未知错误")
            self._yingmi_status.set(f"❌ 失败: {err[:60]}")
            self._yingmi_set_detail(f"❌ 加载失败\n\n{err}\n\n"
                                     f"可能原因:\n"
                                     f"• 东方财富 API 被临时限流\n"
                                     f"• 网络连接问题\n"
                                     f"• akshare 版本过旧\n\n"
                                     f"💡 建议: 稍后重试, 或先重启 App")
            return

        data = result.get("data") or []

        if mode == "rank":
            self._yingmi_render_rank(data, dt)
        elif mode == "search":
            self._yingmi_render_search(data, dt)
        elif mode == "manager":
            self._yingmi_render_manager(data, dt)

    # ── 排行渲染 ──

    def _yingmi_render_rank(self, records: list, dt: float):
        for w in self._yingmi_rank_frame.winfo_children():
            w.destroy()

        if not records:
            self._yingmi_status.set("⚠️ 无数据")
            return

        headers = ("#", "代码", "基金简称", "类型", "近1周", "近1月", "近1年", "今年来", "成立来")
        tree = ttk.Treeview(self._yingmi_rank_frame, columns=headers,
                            show="headings", height=min(30, len(records)))
        widths = (30, 70, 200, 80, 60, 60, 70, 70, 70)
        for h, w in zip(headers, widths):
            tree.heading(h, text=h)
            tree.column(h, width=w, anchor="center" if h not in ("基金简称",) else "w")

        sort_col = self._RANK_MODES[[l for l, _ in self._RANK_MODES].index(self._yingmi_rank_var())][1]
        tree.tag_configure("top5", background="#fff3e0", foreground="#e65100")
        tree.tag_configure("top20", background="#fffde7")

        for i, rec in enumerate(records):
            code = rec.get("基金代码", "")
            name = rec.get("基金简称", "")
            ftype = rec.get("基金类型", "")
            vals = (
                i + 1,
                code,
                name[:28] if len(str(name)) > 28 else name,
                ftype[:10] if len(str(ftype)) > 10 else ftype,
                self._fmt_pct(rec.get("近1周")),
                self._fmt_pct(rec.get("近1月")),
                self._fmt_pct(rec.get("近1年")),
                self._fmt_pct(rec.get("今年来")),
                self._fmt_pct(rec.get("成立来")),
            )
            tag = ""
            if i < 5: tag = "top5"
            elif i < 20: tag = "top20"
            tree.insert("", tk.END, values=vals, tags=(tag,) if tag else ())

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 滚动条
        sb = ttk.Scrollbar(self._yingmi_rank_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # 点击 → 右列详情
        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(records):
                self._yingmi_show_fund_detail(records[idx])

        def _on_double(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(records):
                code = records[idx].get("基金代码", "")
                if code:
                    webbrowser.open_new_tab(
                        f"https://fund.eastmoney.com/{code}.html")

        tree.bind("<<TreeviewSelect>>", _on_select)
        tree.bind("<Double-1>", _on_double)

        self._yingmi_status.set(
            f"✅ 按 {sort_col} 排序: {len(records)} 只 ({dt:.1f}s) | 双击 → 东方财富")

    # ── 搜索渲染 ──

    def _yingmi_render_search(self, records: list, dt: float):
        for w in self._yingmi_tree_frame.winfo_children():
            w.destroy()

        if not records:
            self._yingmi_status.set("⚠️ 无匹配基金")
            self._yingmi_set_detail("⚠️ 没有匹配的基金\n\n"
                                     f"搜索关键词: {self._yingmi_query_ent.get()}\n"
                                     f"试试换个关键词: 白酒、半导体、新能源...")
            return

        headers = ("#", "基金代码", "基金简称", "基金类型")
        tree = ttk.Treeview(self._yingmi_tree_frame, columns=headers,
                            show="headings", height=min(30, len(records)))
        widths = (30, 90, 300, 140)
        for h, w in zip(headers, widths):
            tree.heading(h, text=h)
            tree.column(h, width=w, anchor="w" if h in ("基金简称", "基金类型") else "center")

        for i, rec in enumerate(records):
            code = rec.get("基金代码", "")
            name = rec.get("基金简称", "")
            ftype = rec.get("基金类型", "")
            tree.insert("", tk.END, values=(i + 1, code, name, ftype))

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(self._yingmi_tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(records):
                self._yingmi_show_fund_name_detail(records[idx])

        def _on_double(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(records):
                code = records[idx].get("基金代码", "")
                if code:
                    webbrowser.open_new_tab(
                        f"https://fund.eastmoney.com/{code}.html")

        tree.bind("<<TreeviewSelect>>", _on_select)
        tree.bind("<Double-1>", _on_double)

        self._yingmi_status.set(f"✅ 找到 {len(records)} 只基金 ({dt:.1f}s) | 双击 → 东方财富")

    # ── 基金经理渲染 ──

    def _yingmi_render_manager(self, records: list, dt: float):
        for w in self._yingmi_rank_frame.winfo_children():
            w.destroy()

        if not records:
            self._yingmi_status.set("⚠️ 无数据")
            return

        headers = ("#", "姓名", "所属公司", "现任基金", "规模(亿)", "从业年限", "最佳回报")
        tree = ttk.Treeview(self._yingmi_rank_frame, columns=headers,
                            show="headings", height=min(30, len(records)))
        widths = (30, 80, 160, 140, 80, 70, 90)
        for h, w in zip(headers, widths):
            tree.heading(h, text=h)
            tree.column(h, width=w, anchor="center" if h in ("#", "规模(亿)", "从业年限", "最佳回报") else "w")

        for i, rec in enumerate(records):
            name = rec.get("姓名", "")
            company = rec.get("所属公司", "")
            fund = rec.get("现任基金", "")
            scale = rec.get("现任基金资产总规模", "")
            years = rec.get("累计从业时间", "")
            ret = rec.get("现任基金最佳回报", "")
            tree.insert("", tk.END, values=(i + 1, name, company[:18], fund[:18], scale, years, ret))

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(self._yingmi_rank_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(records):
                self._yingmi_show_manager_detail(records[idx])

        tree.bind("<<TreeviewSelect>>", _on_select)

        self._yingmi_status.set(f"✅ 基金经理 TOP {len(records)} 按规模排序 ({dt:.1f}s)")

    # ═══════════════════════════════════════════════════════════
    # 📖 详情面板
    # ═══════════════════════════════════════════════════════════

    def _yingmi_show_fund_detail(self, rec: dict):
        lines = []
        lines.append(f"📊 {rec.get('基金简称', '')}")
        lines.append(f"{'─' * 40}")
        lines.append(f"🏷️ 基金代码: {rec.get('基金代码', '')}")
        lines.append(f"📁 基金类型: {rec.get('日期', '')}  更新")
        lines.append(f"💰 单位净值: {rec.get('单位净值', '')}")
        lines.append(f"📈 累计净值: {rec.get('累计净值', '')}")
        lines.append(f"📊 日增长率: {rec.get('日增长率', '')}")
        lines.append("")
        lines.append("📉 收益率:")
        for label, key in [("近1周", "近1周"), ("近1月", "近1月"), ("近3月", "近3月"),
                           ("近6月", "近6月"), ("近1年", "近1年"), ("近2年", "近2年"),
                           ("近3年", "近3年"), ("今年以来", "今年来"), ("成立以来", "成立来")]:
            v = rec.get(key, "")
            if v:
                v_str = str(v)
                color = "🟢" if v_str.replace("%", "").replace("-", "").replace(".", "").isdigit() and float(v_str.replace("%", "").replace("-", "0")) > 0 else "🔴"
                lines.append(f"  {label}: {color} {v}")
        lines.append("")
        lines.append(f"💳 手续费: {rec.get('手续费', '')}")
        lines.append("")
        lines.append("🔗 更多信息:")
        code = rec.get("基金代码", "")
        if code:
            lines.append(f"  东方财富: https://fund.eastmoney.com/{code}.html")
        lines.append("  双击列表行直接打开 ↗")
        self._yingmi_set_detail("\n".join(lines))

        # 🆕 异步拉重仓股
        if code:
            self._yingmi_load_holdings(code)

    def _yingmi_show_fund_name_detail(self, rec: dict):
        lines = []
        lines.append(f"📊 {rec.get('基金简称', '')}")
        lines.append(f"{'─' * 40}")
        lines.append(f"🏷️ 基金代码: {rec.get('基金代码', '')}")
        lines.append(f"📁 基金类型: {rec.get('基金类型', '')}")
        lines.append(f"🔤 拼音缩写: {rec.get('拼音缩写', '')}")
        lines.append("")
        lines.append("💡 提示:")
        lines.append("  选中后点击 🏆排行 查看收益率详情")
        code = rec.get("基金代码", "")
        if code:
            lines.append(f"  或双击打开: https://fund.eastmoney.com/{code}.html")
        self._yingmi_set_detail("\n".join(lines))

    def _yingmi_show_manager_detail(self, rec: dict):
        lines = []
        lines.append(f"👔 {rec.get('姓名', '')}")
        lines.append(f"{'─' * 40}")
        lines.append(f"🏢 所属公司: {rec.get('所属公司', '')}")
        lines.append(f"💼 现任基金: {rec.get('现任基金', '')}")
        lines.append(f"🆔 现任基金代码: {rec.get('现任基金代码', '')}")
        lines.append(f"⏳ 累计从业: {rec.get('累计从业时间', '')}")
        lines.append(f"💰 基金规模: {rec.get('现任基金资产总规模', '')}")
        lines.append(f"🏆 最佳回报: {rec.get('现任基金最佳回报', '')}")
        self._yingmi_set_detail("\n".join(lines))

    # ── 工具函数 ──

    def _fmt_pct(self, val) -> str:
        if val is None or val == "":
            return "-"
        s = str(val)
        if s == "-":
            return "-"
        return s if "%" in s else s + "%"

    def _yingmi_set_detail(self, text: str):
        self._yingmi_detail_text.configure(state=tk.NORMAL)
        self._yingmi_detail_text.delete("1.0", tk.END)
        self._yingmi_detail_text.insert("1.0", text)
        self._yingmi_detail_text.configure(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════
    # 📦 重仓股加载 + 渲染
    # ═══════════════════════════════════════════════════════════

    def _yingmi_load_holdings(self, fund_code: str):
        """异步拉取基金前十大重仓股"""
        # 先清空旧数据, 显示 loading
        for w in self._yingmi_hold_tree_frame.winfo_children(): w.destroy()
        ttk.Label(self._yingmi_hold_tree_frame,
                  text="⏳ 加载重仓股...", font=("", 12), foreground="gray")\
            .pack(expand=True)
        self._yingmi_hold_tree_frame.update()

        def _bg():
            try:
                import requests, re
                from bs4 import BeautifulSoup
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": f"https://fundf10.eastmoney.com/ccmx_{fund_code}.html",
                }
                # 先试 2025 Q4, 不行试 2025 / 2024 其他季度
                data = None
                for year in ["2025", "2024", "2026"]:
                    url = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
                    params = {"type": "jjcc", "code": fund_code, "topline": "100",
                              "year": year, "month": "", "rt": f"{time.time():.16f}"}
                    r = requests.get(url, params=params, headers=headers, timeout=15)
                    if r.status_code != 200 or len(r.text) < 500: continue
                    # 解析 var apidata={ content:"...", errcode:"" }
                    m = re.search(r'var\s+apidata\s*=\s*\{(.*)\};?\s*$', r.text, re.DOTALL)
                    if not m: continue
                    raw_obj = "{" + m.group(1) + "}"
                    # 简单提取 content 字符串
                    cm = re.search(r'content\s*:\s*"((?:[^"\\]|\\.)*)"', raw_obj)
                    if not cm: continue
                    import codecs
                    html_content = codecs.decode(cm.group(1), 'unicode_escape')
                    # 找所有 h4.t (报告期) 和 table
                    soup = BeautifulSoup(html_content, "lxml")
                    item_labels = [h.get_text(strip=True).split("20")[0] for h in soup.find_all("h4", class_="t")]
                    tables = soup.find_all("table")
                    if not tables: continue
                    # 取最新报告期的第一张表
                    rows = tables[0].find_all("tr")
                    holdings = []
                    for row in rows[1:11]:  # 表头跳过, 取前 10 行
                        tds = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
                        if len(tds) >= 5 and tds[1]:  # 要有股票代码
                            # tds: [序号, 股票代码, 股票名称, 占净值比例, 持股数(万股), 持仓市值(万元)]
                            holdings.append({
                                "序号": tds[0],
                                "股票代码": tds[1],
                                "股票名称": tds[2],
                                "占净值比例": tds[3].replace("%", ""),
                                "持股数": tds[4],
                                "持仓市值": tds[5] if len(tds) > 5 else "",
                            })
                    if holdings:
                        data = {"holdings": holdings, "period": item_labels[0] if item_labels else "最新"}
                        break
                self.root.after(0, lambda: self._yingmi_render_holdings(
                    data if data else {"holdings": [], "error": "暂无持仓数据"}))
            except Exception as e:
                self.root.after(0, lambda: self._yingmi_render_holdings(
                    {"holdings": [], "error": f"❌ 加载失败: {type(e).__name__}: {str(e)[:100]}"}))
        threading.Thread(target=_bg, daemon=True).start()

    def _yingmi_render_holdings(self, data: dict):
        for w in self._yingmi_hold_tree_frame.winfo_children(): w.destroy()

        holdings = data.get("holdings", [])
        period = data.get("period", "")
        err = data.get("error", "")

        if err or not holdings:
            msg = err or f"⚠️ 该基金暂无重仓股数据\n\n原因: {err}"
            ttk.Label(self._yingmi_hold_tree_frame, text=msg,
                      font=("", 11), wraplength=400,
                      foreground="#555", justify=tk.LEFT).pack(padx=10, pady=20)
            return

        # 标题
        ttk.Label(self._yingmi_hold_tree_frame,
                  text=f"📦 {period} · 前 {len(holdings)} 大重仓股",
                  font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(2, 4))

        headers = ("#", "股票代码", "股票名称", "占净值比例", "持股数(万)", "持仓市值(万)")
        tree = ttk.Treeview(self._yingmi_hold_tree_frame, columns=headers,
                            show="headings", height=min(12, len(holdings)))
        widths = (30, 80, 140, 90, 100, 110)
        for h, w in zip(headers, widths):
            tree.heading(h, text=h); tree.column(h, width=w, anchor="center")

        for i, h in enumerate(holdings):
            pct = h.get("占净值比例", "0")
            try:
                pct_val = float(pct) if pct else 0
            except Exception:
                pct_val = 0
            tag = ("top1",) if i == 0 else ("top3",) if pct_val >= 8 else ()
            tree.insert("", tk.END, values=(
                i + 1, h.get("股票代码", ""), h.get("股票名称", ""),
                f"{pct_val:.2f}%", h.get("持股数", ""), h.get("持仓市值", "")),
                tags=tag)
        tree.tag_configure("top1", background="#fff3e0", foreground="#e65100", font=("", 10, "bold"))
        tree.tag_configure("top3", background="#fffde7")

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(self._yingmi_hold_tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set); sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _sel(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(holdings):
                h = holdings[idx]
                line = (f"📦 重仓股详情\n{'─'*40}\n"
                        f"  股票代码: {h.get('股票代码','')}\n"
                        f"  股票名称: {h.get('股票名称','')}\n"
                        f"  占净值比例: {h.get('占净值比例','')}%\n"
                        f"  持股数(万股): {h.get('持股数','')}\n"
                        f"  持仓市值(万元): {h.get('持仓市值','')}\n\n"
                        f"💡 双击打开日K线图")
                self._yingmi_set_detail(line)

        def _dbl(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(holdings):
                h = holdings[idx]
                code = h.get("股票代码", "")
                name = h.get("股票名称", "")
                if code:
                    self._yingmi_open_kline(code, name)

        tree.bind("<<TreeviewSelect>>", _sel)
        tree.bind("<Double-1>", _dbl)

    # ═══════════════════════════════════════════════════════════
    # 📈 日 K 线图弹窗 (matplotlib + tushare)
    # ═══════════════════════════════════════════════════════════

    def _yingmi_open_kline(self, code: str, name: str):
        """弹出日 K 线图 + MA + MACD + 成交量"""
        dlg = tk.Toplevel(self.root)
        dlg.title(f"📈 日K线 · {name} ({code})")
        dlg.geometry("1100x720")

        # 先显示 loading
        load_lbl = ttk.Label(dlg, text=f"⏳ 加载 {name} 日K线数据...",
                              font=("", 12))
        load_lbl.pack(expand=True)

        def _bg():
            try:
                import os, numpy as np
                import tushare as ts
                from datetime import datetime, timedelta

                # 确定 ts_code
                if code.startswith("6"): ts_code = f"{code}.SH"
                elif code[0] in "032": ts_code = f"{code}.SZ"
                elif code.startswith("8") or code.startswith("4"): ts_code = f"{code}.BJ"
                else: ts_code = code + ".SH"

                token = os.getenv("TUSHARE_TOKEN", "")
                if not token:
                    self.root.after(0, lambda: self._yingmi_kline_fail(
                        dlg, "⚠️ 需要 TUSHARE_TOKEN 才能画 K 线"))
                    return
                ts.set_token(token)
                pro = ts.pro_api()

                end = datetime.now().strftime("%Y%m%d")
                start = (datetime.now() - timedelta(days=250)).strftime("%Y%m%d")
                df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
                if df is None or df.empty:
                    self.root.after(0, lambda: self._yingmi_kline_fail(
                        dlg, f"⚠️ {name} 日线数据为空"))
                    return

                df = df.sort_values("trade_date").reset_index(drop=True)
                self.root.after(0, lambda: self._yingmi_render_kline(
                    dlg, name, code, df))
            except Exception as e:
                self.root.after(0, lambda: self._yingmi_kline_fail(
                    dlg, f"❌ 加载失败: {type(e).__name__}: {str(e)[:100]}"))
        threading.Thread(target=_bg, daemon=True).start()

    def _yingmi_kline_fail(self, dlg, msg):
        for w in dlg.winfo_children(): w.destroy()
        ttk.Label(dlg, text=msg, font=("", 12),
                  wraplength=500, justify=tk.CENTER,
                  foreground="#c62828").pack(expand=True, padx=20, pady=40)

    def _yingmi_render_kline(self, dlg, name, code, df):
        """用 matplotlib 画 K 线 + MA + MACD + 成交量"""
        for w in dlg.winfo_children(): w.destroy()

        import numpy as np
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        import matplotlib.dates as mdates
        from matplotlib.patches import Rectangle
        from datetime import datetime

        n = len(df)
        dates = [datetime.strptime(d, "%Y%m%d") for d in df["trade_date"]]
        open_p = df["open"].values
        high_p = df["high"].values
        low_p = df["low"].values
        close_p = df["close"].values
        vol = df["vol"].values / 10000  # 万手

        # 均线
        def sma(arr, w):
            if len(arr) < w: return np.array([np.nan]*len(arr))
            r = np.full(len(arr), np.nan)
            for i in range(w-1, len(arr)): r[i] = np.mean(arr[i-w+1:i+1])
            return r
        ma5 = sma(close_p, 5)
        ma10 = sma(close_p, 10)
        ma20 = sma(close_p, 20)
        ma60 = sma(close_p, 60)

        # MACD
        def ema(arr, w):
            alpha = 2/(w+1); r = np.zeros(len(arr)); r[0] = arr[0]
            for i in range(1, len(arr)): r[i] = alpha*arr[i] + (1-alpha)*r[i-1]
            return r
        ema12 = ema(close_p, 12); ema26 = ema(close_p, 26)
        dif = ema12 - ema26; dea = ema(dif, 9); macd = (dif - dea) * 2

        fig = Figure(figsize=(11, 7), dpi=100, facecolor="#f5f5f5")
        # 4 行子图, 高度比 4:1.5:1:1.5
        gs = fig.add_gridspec(4, 1, height_ratios=[4, 1.5, 1, 1.5], hspace=0.05)
        ax_k = fig.add_subplot(gs[0, 0])   # K线 + MA
        ax_m = fig.add_subplot(gs[1, 0], sharex=ax_k)  # MACD
        ax_v = fig.add_subplot(gs[2, 0], sharex=ax_k)  # 成交量
        ax_ma2 = fig.add_subplot(gs[3, 0], sharex=ax_k)  # MA 对比

        x = np.arange(n)
        # ── K 线 (简化版: 红绿矩形 + 影线) ──
        colors = ["#d32f2f" if close_p[i] >= open_p[i] else "#2e7d32" for i in range(n)]
        for i in range(n):
            c = colors[i]
            ax_k.plot([x[i], x[i]], [low_p[i], high_p[i]], color=c, lw=0.8)  # 影线
            body = abs(close_p[i] - open_p[i])
            if body < 0.01: body = 0.01
            bottom = min(open_p[i], close_p[i])
            rect = Rectangle((x[i]-0.35, bottom), 0.7, body, color=c)
            ax_k.add_patch(rect)

        # MA
        ax_k.plot(x, ma5, label="MA5", color="#ff9800", lw=1); ax_k.plot(x, ma10, label="MA10", color="#2196f3", lw=1)
        ax_k.plot(x, ma20, label="MA20", color="#9c27b0", lw=1); ax_k.plot(x, ma60, label="MA60", color="#795548", lw=1)
        ax_k.set_title(f"📈 {name} ({code})  日线 K 线图  ·  近 {n} 日", fontsize=13, fontweight="bold", pad=8)
        ax_k.legend(loc="upper left", fontsize=8, ncol=4)
        ax_k.grid(alpha=0.2)
        ax_k.set_ylabel("价格")
        ax_k.tick_params(axis="x", labelbottom=False)

        # ── MACD ──
        ax_m.bar(x, np.where(macd >= 0, macd, 0), color="#d32f2f", width=0.6)
        ax_m.bar(x, np.where(macd < 0, macd, 0), color="#2e7d32", width=0.6)
        ax_m.plot(x, dif, label="DIF", color="#ff9800", lw=1); ax_m.plot(x, dea, label="DEA", color="#2196f3", lw=1)
        ax_m.axhline(0, color="gray", lw=0.5); ax_m.grid(alpha=0.2)
        ax_m.set_ylabel("MACD"); ax_m.legend(loc="upper left", fontsize=8); ax_m.tick_params(axis="x", labelbottom=False)

        # ── 成交量 ──
        ax_v.bar(x, vol, color=["#d32f2f" if close_p[i] >= open_p[i] else "#2e7d32" for i in range(n)], width=0.6)
        ax_v.set_ylabel("万手"); ax_v.grid(alpha=0.2)
        ax_v.tick_params(axis="x", labelbottom=False)

        # ── MA 对比 ──
        ax_ma2.plot(x, close_p, label="收盘价", color="#333", lw=1.2)
        ax_ma2.plot(x, ma5, color="#ff9800", lw=1); ax_ma2.plot(x, ma10, color="#2196f3", lw=1)
        ax_ma2.plot(x, ma20, color="#9c27b0", lw=1); ax_ma2.plot(x, ma60, color="#795548", lw=1)
        # 日期轴
        tick_step = max(1, n // 12)
        ax_ma2.set_xticks(x[::tick_step])
        ax_ma2.set_xticklabels([dates[i].strftime("%m-%d") for i in range(0, n, tick_step)], rotation=45, fontsize=8)
        ax_ma2.set_ylabel("MA对比"); ax_ma2.grid(alpha=0.2)

        # 右上角显示最新价
        last = close_p[-1]
        chg = (close_p[-1] - close_p[-2]) / close_p[-2] * 100 if n > 1 else 0
        chg_color = "#d32f2f" if chg >= 0 else "#2e7d32"
        fig.text(0.92, 0.96, f"最新 {last:.2f}  {chg:+.2f}%",
                 ha="right", fontsize=11, color=chg_color, fontweight="bold")

        # 嵌入 Tk
        canvas = FigureCanvasTkAgg(fig, master=dlg)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 底部按钮
        btn_bar = ttk.Frame(dlg)
        btn_bar.pack(fill=tk.X, padx=10, pady=6)
        ttk.Button(btn_bar, text="🔗 东方财富",
                   command=lambda: webbrowser.open(
                       f"https://quote.eastmoney.com/{'sh' if code.startswith('6') else 'sz'}{code}.html")
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="🔗 同花顺",
                   command=lambda: webbrowser.open(
                       f"https://stockpage.10jqka.com.cn/{code}/")
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="📊 导出数据",
                   command=lambda: self._yingmi_export_kline(code, df)
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="❌ 关闭", command=dlg.destroy).pack(side=tk.RIGHT)

    def _yingmi_export_kline(self, code, df):
        path = os.path.expanduser(f"~/Downloads/{code}_kline.csv")
        df.to_csv(path, index=False)
        tk.messagebox.showinfo("导出成功", f"✅ 已保存到:\n{path}")
