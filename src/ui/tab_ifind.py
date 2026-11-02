"""同花顺 iFinD 数据弹窗 Mixin"""
from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import ttk

from utils.ifind_client import (
    AUTH_TOKEN,
    ETF_SYMBOLS_DEFAULT,
    INDEX_SYMBOLS_DEFAULT,
    TRENDING_SIZE_DEFAULT,
    etf_realtime,
    index_realtime,
    parse_tables,
    sector_today,
    stock_realtime,
    trending_news,
)


class IfindMixin:
    """iFinD 同花顺数据弹窗"""

    # ── 左列功能定义: key → (label, 取数函数, 额外参数构造) ──
    _IFIND_FEATURES = [
        ("index", "📊 大盘指数实时", "_feat_index"),
        ("stock", "📈 热门个股快查", "_feat_stock"),
        ("etf", "💹 热门ETF行情", "_feat_etf"),
        ("sector", "🏭 行业板块今日", "_feat_sector"),
        ("news", "📰 热点资讯(24h)", "_feat_news"),
        ("search", "🔍 新闻语义搜索", "_feat_search"),
    ]

    # 热门个股池
    _HOT_STOCKS = "600519.SH,000858.SZ,300750.SZ,601318.SH,002594.SZ,600036.SH,000333.SZ,601899.SH,601012.SH,000725.SZ"

    def _show_ths_ifind_dialog(self):
        """🔷 同花顺 iFinD 当日数据弹窗 - 三列 PanedWindow"""
        _dlg = tk.Toplevel(self.root)
        _dlg.title("🔷 同花顺 iFinD · 当日行情")
        _dlg.geometry("1280x760")
        _dlg.transient(self.root)

        # ── 顶栏: 刷新按钮 + 状态 ──
        _topbar = ttk.Frame(_dlg)
        _topbar.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(_topbar, text="🔷 同花顺 iFinD 金融数据",
                  font=("TkDefaultFont", 13, "bold")).pack(side=tk.LEFT)
        self._ifind_status = tk.StringVar(value="准备加载...")
        ttk.Label(_topbar, textvariable=self._ifind_status,
                  foreground="gray").pack(side=tk.LEFT, padx=12)
        ttk.Button(_topbar, text="🔄 刷新全部", width=10,
                   command=lambda: self._ifind_refresh_all(_dlg)).pack(side=tk.RIGHT)

        # ── 三列 PanedWindow ──
        _pw = ttk.PanedWindow(_dlg, orient=tk.HORIZONTAL)
        _pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── 左列: 功能入口 ──
        _left = ttk.Frame(_pw, width=180)
        _pw.add(_left, weight=0)
        ttk.Label(_left, text="📋 功能入口",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=4, pady=(4, 2))
        _lb_frame = ttk.Frame(_left)
        _lb_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self._ifind_feat_lb = tk.Listbox(_lb_frame, selectmode=tk.SINGLE,
                                         font=("TkDefaultFont", 11),
                                         activestyle="dotbox", exportselection=False)
        for _, lbl, _ in self._IFIND_FEATURES:
            self._ifind_feat_lb.insert(tk.END, lbl)
        self._ifind_feat_lb.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        _sb = ttk.Scrollbar(_lb_frame, orient=tk.VERTICAL, command=self._ifind_feat_lb.yview)
        _sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._ifind_feat_lb.configure(yscrollcommand=_sb.set)
        self._ifind_feat_lb.bind("<<ListboxSelect>>",
                                 lambda e: self._ifind_on_feat_select(_dlg))

        # ── 中列: 数据表格 ──
        _mid = ttk.Frame(_pw)
        _pw.add(_mid, weight=3)
        self._ifind_tree_frame = ttk.Frame(_mid)
        self._ifind_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._ifind_tree = None  # 动态创建

        # ── 右列: 市场概况 ──
        _right = ttk.Frame(_pw, width=320)
        _pw.add(_right, weight=2)

        # 右列-上: 大盘指数卡片
        _idx_frame = tk.LabelFrame(_right, text="📊 大盘指数",
                                    font=("TkDefaultFont", 11, "bold"))
        _idx_frame.pack(fill=tk.X, padx=4, pady=4)
        self._ifind_idx_labels = {}
        for _code, _name in [("000001.SH", "上证指数"), ("399001.SZ", "深证成指"),
                             ("399006.SZ", "创业板指"), ("000688.SH", "科创50")]:
            _row = ttk.Frame(_idx_frame)
            _row.pack(fill=tk.X, padx=6, pady=2)
            ttk.Label(_row, text=_name, width=8,
                      font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
            _price_lbl = ttk.Label(_row, text="--", width=9, anchor="e",
                                    font=("TkDefaultFont", 12, "bold"))
            _price_lbl.pack(side=tk.LEFT, padx=(4, 6))
            _pct_lbl = tk.Label(_row, text="--", width=8, anchor="e",
                                font=("TkDefaultFont", 11, "bold"))
            _pct_lbl.pack(side=tk.LEFT)
            _nums_lbl = ttk.Label(_row, text="", anchor="e", foreground="gray",
                                   font=("TkDefaultFont", 9))
            _nums_lbl.pack(side=tk.RIGHT)
            self._ifind_idx_labels[_code] = {
                "price": _price_lbl, "pct": _pct_lbl, "nums": _nums_lbl
            }

        # 右列-中: 涨跌家数
        _cnt_frame = tk.LabelFrame(_right, text="📈 涨跌统计",
                                    font=("TkDefaultFont", 11, "bold"))
        _cnt_frame.pack(fill=tk.X, padx=4, pady=4)
        self._ifind_cnt_labels = {}
        for _key, _name, _fg in [("rise", "上涨家数", "#d32f2f"),
                                  ("fall", "下跌家数", "#388e3c"),
                                  ("up", "涨停", "#ff5722"),
                                  ("down", "跌停", "#009688")]:
            _r = ttk.Frame(_cnt_frame)
            _r.pack(fill=tk.X, padx=6, pady=1)
            ttk.Label(_r, text=_name, width=8).pack(side=tk.LEFT)
            _v = tk.Label(_r, text="--", anchor="e", width=8,
                          foreground=_fg, font=("TkDefaultFont", 12, "bold"))
            _v.pack(side=tk.RIGHT)
            self._ifind_cnt_labels[_key] = _v

        # 右列-下: 热点资讯
        _news_frame = tk.LabelFrame(_right, text="📰 热点资讯 Top 5",
                                      font=("TkDefaultFont", 11, "bold"))
        _news_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._ifind_news_text = tk.Text(_news_frame, height=8, wrap=tk.WORD,
                                        font=("TkDefaultFont", 10),
                                        background="#fafafa", borderwidth=0)
        self._ifind_news_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._ifind_news_text.configure(state=tk.DISABLED)

        # ── 自动加载: 大盘指数 + 热点资讯 + 默认选中第一项 ──
        if not AUTH_TOKEN:
            self._ifind_status.set("⚠️ 未授权 iFinD, 请在 Trae 插件里授权")
        else:
            self._ifind_refresh_all(_dlg)
            self._ifind_feat_lb.selection_set(0)
            self._ifind_on_feat_select(_dlg)

    # ── 刷新全部: 后台线程取指数 + 资讯 ──
    def _ifind_refresh_all(self, dlg):
        self._ifind_status.set("⏳ 正在加载 iFinD 数据...")

        def _bg():
            # 1. 大盘指数
            r_idx = index_realtime(INDEX_SYMBOLS_DEFAULT)
            # 2. 热点资讯
            r_news = trending_news(size=TRENDING_SIZE_DEFAULT)
            # 回主线程
            self.root.after(0, lambda: self._ifind_fill_right(r_idx, r_news))

        threading.Thread(target=_bg, daemon=True).start()

    # ── 填充右列(指数卡片 + 涨跌 + 资讯) ──
    def _ifind_fill_right(self, r_idx, r_news):
        # ── 指数卡片 ──
        if r_idx.get("ok"):
            header, rows = parse_tables(r_idx.get("data", {}))
            for row in rows:
                try:
                    _code = row[0]
                    _price = float(row[3])
                    _pct = float(row[4])
                    if _code in self._ifind_idx_labels:
                        self._ifind_idx_labels[_code]["price"].configure(
                            text=f"{_price:.2f}")
                        _pct_txt = f"{_pct:+.2f}%"
                        _fg = "#d32f2f" if _pct > 0 else ("#388e3c" if _pct < 0 else "#555")
                        self._ifind_idx_labels[_code]["pct"].configure(
                            text=_pct_txt, foreground=_fg)
                        # 涨跌家数 (row[6]=rise, row[7]=fall, row[8]=upLimit, row[9]=downLimit)
                        if len(row) > 9:
                            self._ifind_idx_labels[_code]["nums"].configure(
                                text=f"↑{row[6]} ↓{row[7]}")
                except (ValueError, IndexError, TypeError):
                    pass
            # 从第一行(上证指数)提取涨跌家数
            if rows:
                try:
                    self._ifind_cnt_labels["rise"].configure(text=rows[0][6])
                    self._ifind_cnt_labels["fall"].configure(text=rows[0][7])
                    self._ifind_cnt_labels["up"].configure(text=rows[0][8])
                    self._ifind_cnt_labels["down"].configure(text=rows[0][9])
                except (IndexError, TypeError):
                    pass

        # ── 热点资讯 ──
        if r_news.get("ok"):
            _d = r_news.get("data", {})
            _d2 = _d.get("data", {}) if isinstance(_d, dict) else {}
            items = _d2.get("result", []) if isinstance(_d2, dict) else []
            self._ifind_news_text.configure(state=tk.NORMAL)
            self._ifind_news_text.delete("1.0", tk.END)
            for i, it in enumerate(items[:5], 1):
                _title = it.get("资讯标题", "?")
                _src = it.get("信息来源", "")
                _hot = it.get("资讯热度", "")
                self._ifind_news_text.insert(tk.END, f"{i}. {_title}\n", "title")
                self._ifind_news_text.insert(
                    tk.END, f"   来源:{_src}  热度:{_hot}\n\n")
            self._ifind_news_text.tag_configure("title",
                                                 font=("TkDefaultFont", 10, "bold"))
            self._ifind_news_text.configure(state=tk.DISABLED)

        self._ifind_status.set("✅ 数据已更新")

    # ── 左列选中联动: 取数 + 渲染表格 ──
    def _ifind_on_feat_select(self, dlg):
        _sel = self._ifind_feat_lb.curselection()
        if not _sel:
            return
        _idx = _sel[0]
        _key, _label, _handler = self._IFIND_FEATURES[_idx]
        self._ifind_status.set(f"⏳ 加载 {_label}...")

        # 先清空中列 + 显示 "加载中..."
        self._ifind_clear_mid()
        self._ifind_show_mid_loading(_label)

        def _bg():
            r = {}
            try:
                if _key == "index":
                    r = index_realtime(INDEX_SYMBOLS_DEFAULT)
                elif _key == "stock":
                    r = stock_realtime(self._HOT_STOCKS)
                elif _key == "etf":
                    r = etf_realtime(ETF_SYMBOLS_DEFAULT)
                elif _key == "sector":
                    r = sector_today()
                elif _key == "news":
                    r = trending_news(size=TRENDING_SIZE_DEFAULT)
                elif _key == "search":
                    # search 需要用户输入 query — 暂不自动触发,提示用户
                    self.root.after(0, lambda: self._ifind_show_mid_text(
                        "🔍 新闻语义搜索\n\n请在左列选择其他功能,或在代码中设置搜索关键词。\n\n示例:\n  query='人工智能行业动态'\n  query='新能源汽车销量'"))
                    return
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            self.root.after(0, lambda: self._ifind_render_mid(_key, _label, r))

        threading.Thread(target=_bg, daemon=True).start()

    # ── 中列渲染辅助 ──
    def _ifind_clear_mid(self):
        for w in self._ifind_tree_frame.winfo_children():
            w.destroy()
        self._ifind_tree = None

    def _ifind_show_mid_loading(self, label):
        ttk.Label(self._ifind_tree_frame,
                  text=f"⏳ 正在加载 {label}...",
                  font=("TkDefaultFont", 12)).pack(pady=40)

    def _ifind_show_mid_text(self, text):
        self._ifind_clear_mid()
        _txt = tk.Text(self._ifind_tree_frame, wrap=tk.WORD, height=20,
                       font=("TkDefaultFont", 11), background="#fafafa")
        _txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        _txt.insert("1.0", text)
        _txt.configure(state=tk.DISABLED)

    def _ifind_render_mid(self, key, label, r):
        self._ifind_clear_mid()

        if not r.get("ok"):
            self._ifind_show_mid_text(
                f"❌ 加载失败: {label}\n\n错误: {r.get('error', '未知错误')}")
            self._ifind_status.set(f"❌ {label} 加载失败")
            return

        # news 类型特殊处理(有资讯列表)
        if key in ("news", "search"):
            _d = r.get("data", {})
            _d2 = _d.get("data", {}) if isinstance(_d, dict) else {}
            items = _d2.get("result", []) if isinstance(_d2, dict) else []
            self._ifind_render_news_table(items)
            self._ifind_status.set(f"✅ {label}: {len(items)} 条")
            return

        # 标准 tables 格式
        header, rows = parse_tables(r.get("data", {}))
        if not header:
            self._ifind_show_mid_text(f"⚠️ {label}\n\n暂无数据返回,可能非交易时段或查询条件无匹配。")
            self._ifind_status.set(f"⚠️ {label} 无数据")
            return

        self._ifind_render_data_table(header, rows, key)
        self._ifind_status.set(f"✅ {label}: {len(rows)} 条")

    # ── 通用数据表格 ──
    def _ifind_render_data_table(self, header, rows, key):
        # 列宽估计
        _cols = list(range(len(header)))
        _headings = header
        _widths = [100] * len(header)
        for i, h in enumerate(header):
            _widths[i] = max(60, min(200, len(str(h)) * 14))

        tree = ttk.Treeview(self._ifind_tree_frame, columns=_cols, show="headings",
                            height=min(20, max(5, len(rows))))
        for i, (h, w) in enumerate(zip(_headings, _widths)):
            tree.heading(i, text=h)
            tree.column(i, width=w, anchor="center", stretch=True)

        # 颜色 tag: 涨红跌绿
        tree.tag_configure("up", foreground="#d32f2f")
        tree.tag_configure("down", foreground="#388e3c")

        for row in rows:
            _vals = []
            _tag = ""
            for i, v in enumerate(row):
                # 数值格式化
                try:
                    _f = float(v)
                    # 成交额 -> 亿
                    if "成交额" in header[i] or "amount" in str(header[i]).lower():
                        _vals.append(f"{_f / 1e8:.1f}亿")
                    elif header[i] == "涨跌幅" or header[i] == "changeRatio":
                        _vals.append(f"{_f:+.2f}%")
                        _tag = "up" if _f > 0 else ("down" if _f < 0 else "")
                    elif header[i] == "折价":
                        _vals.append(f"{_f * 100:.2f}%")
                    elif abs(_f) >= 1e8:
                        _vals.append(f"{_f / 1e8:.2f}亿")
                    elif abs(_f) >= 1e4:
                        _vals.append(f"{_f / 1e4:.1f}万")
                    else:
                        _vals.append(f"{_f:.2f}" if isinstance(v, float) else str(v))
                except (ValueError, TypeError):
                    _vals.append(str(v) if v is not None else "")
            tree.insert("", tk.END, values=_vals, tags=(_tag,) if _tag else ())

        # 滚动条
        _vsb = ttk.Scrollbar(self._ifind_tree_frame, orient=tk.VERTICAL,
                             command=tree.yview)
        _hsb = ttk.Scrollbar(self._ifind_tree_frame, orient=tk.HORIZONTAL,
                             command=tree.xview)
        tree.configure(yscrollcommand=_vsb.set, xscrollcommand=_hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        _vsb.grid(row=0, column=1, sticky="ns")
        _hsb.grid(row=1, column=0, sticky="ew")
        self._ifind_tree_frame.rowconfigure(0, weight=1)
        self._ifind_tree_frame.columnconfigure(0, weight=1)
        self._ifind_tree = tree

        # 🆕 双击联动 → 打开日K线图
        tree.bind("<Double-1>", lambda e, h=header: self._on_ifind_stock_double(e, h))

    # ── 新闻列表表格 ──
    def _ifind_render_news_table(self, items):
        if not items:
            self._ifind_show_mid_text("⚠️ 暂无资讯数据")
            return

        tree = ttk.Treeview(self._ifind_tree_frame,
                            columns=("title", "source", "hot", "content"),
                            show="headings", height=min(15, len(items)))
        tree.heading("title", text="📰 标题")
        tree.heading("source", text="来源")
        tree.heading("hot", text="热度")
        tree.heading("content", text="摘要")
        tree.column("title", width=280, anchor="w")
        tree.column("source", width=80, anchor="center")
        tree.column("hot", width=70, anchor="e")
        tree.column("content", width=400, anchor="w")

        for it in items:
            _title = it.get("资讯标题", "?")
            _src = it.get("信息来源", "")
            _hot = it.get("资讯热度", "")
            _content = (it.get("资讯内容") or "")[:120] + "..."
            tree.insert("", tk.END, values=(_title, _src, _hot, _content))

        _vsb = ttk.Scrollbar(self._ifind_tree_frame, orient=tk.VERTICAL,
                             command=tree.yview)
        tree.configure(yscrollcommand=_vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        _vsb.grid(row=0, column=1, sticky="ns")
        self._ifind_tree_frame.rowconfigure(0, weight=1)
        self._ifind_tree_frame.columnconfigure(0, weight=1)
        self._ifind_tree = tree  # 🆕 保存引用, 供外部操作

        # 🆕 双击新闻 → 打开原链接
        tree.bind("<Double-1>", lambda e, its=items: self._on_ifind_news_double(e, its))

    # ══════════════════════════════════════════════════
    # 🆕 双击联动回调
    # ══════════════════════════════════════════════════

    def _on_ifind_stock_double(self, event, header):
        """中列表格双击股票 → 后台拉K线 + 弹窗显示"""
        tree = event.widget
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0], "values")
        if not vals or len(vals) < 2:
            return

        # 找到证券代码和名称列 (表头里找)
        try:
            _code_idx = header.index("证券代码")
            _name_idx = header.index("证券简称")
        except ValueError:
            return
        ts_code = str(vals[_code_idx]).strip()
        sname = str(vals[_name_idx]).strip()
        if not ts_code or "." not in ts_code:
            return

        # ts_code → sina (600519.SH → sh600519)
        _base, _suf = ts_code.split(".", 1)
        sina_code = ("sh" if _suf.upper() == "SH" else
                     ("sz" if _suf.upper() == "SZ" else
                      ("bj" if _suf.upper() == "BJ" else ""))) + _base
        if not sina_code:
            return

        # 后台线程拉 K 线 → 弹窗
        self._ifind_status.set(f"⏳ 加载 {sname} K线...")

        def _bg():
            try:
                kdata = self._get_daily_kline_data_tushare(sina_code, days=120)
            except Exception as ex:
                self.root.after(0, lambda: self._ifind_status.set(
                    f"❌ K线加载失败: {ex}"))
                return
            if not kdata:
                self.root.after(0, lambda: self._ifind_status.set(
                    f"⚠️ {sname} K线无数据"))
                return
            self.root.after(0, lambda: self._show_daily_kline_zoom(kdata, sname))
            self.root.after(0, lambda: self._ifind_status.set(f"✅ {sname} K线已打开"))

        threading.Thread(target=_bg, daemon=True).start()

    def _on_ifind_news_double(self, event, items):
        """新闻列表双击 → 打开原链接 (macOS: webbrowser.open 兜底 osascript)"""
        tree = event.widget
        sel = tree.selection()
        if not sel:
            return
        idx = tree.index(sel[0])
        if not (0 <= idx < len(items)):
            return
        url = (items[idx].get("URL") or items[idx].get("url") or "").strip()
        if not url:
            self._ifind_status.set("⚠️ 此条资讯无原文链接")
            return
        # 兜底: webbrowser 返回 False 时用 macOS `open` 命令
        try:
            import webbrowser
            ok = webbrowser.open_new_tab(url)
            if not ok:
                raise RuntimeError("webbrowser returned False")
        except Exception:
            import subprocess, shlex
            try:
                subprocess.Popen(["open", url])  # macOS 兜底
            except Exception:
                self._ifind_status.set(f"❌ 打开链接失败: {url[:60]}")
                return
        self._ifind_status.set("✅ 已在浏览器中打开")


