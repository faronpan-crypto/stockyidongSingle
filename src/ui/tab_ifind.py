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
    fetch_edb,
    get_stock_summary,
    index_realtime,
    parse_markdown_table,
    parse_tables,
    search_edb,
    search_news as _search_news_mcp,
    search_notice,
    search_securities,
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
        ("notice", "📋 上市公司公告", "_feat_notice"),
        ("search_stock", "🎯 智能选股(自然语言)", "_feat_search_stock"),
        ("summary", "📖 股票基本面摘要", "_feat_summary"),
        ("macro", "🌏 宏观经济数据", "_feat_macro"),
        ("macro_search", "🔎 宏观指标搜索", "_feat_macro_search"),
        ("search", "🔍 新闻语义搜索", "_feat_search"),
        ("multi_search", "🧠 多引擎搜索聚合", "_feat_multi_search"),  # 🆕
        ("community_hot", "📺 雪球热帖 + 知乎热榜", "_feat_community_hot"),  # 🆕
    ]

    # 热门个股池
    _HOT_STOCKS = "600519.SH,000858.SZ,300750.SZ,601318.SH,002594.SZ,600036.SH,000333.SZ,601899.SH,601012.SH,000725.SZ"

    # 🆕 多引擎搜索的站点定义 (key, label, url_template)
    _MULTI_SEARCH_ENGINES = [
        ("zhihu", "💬 知乎", "https://www.zhihu.com/search?type=content&q={q}"),
        ("xueqiu", "📱 雪球", "https://xueqiu.com/query/v1/suggest.json?keyword={q}"),
        ("xueqiu_stock", "📈 雪球股票讨论", "https://xueqiu.com/k?q={q}"),
        ("dfcf", "📊 东方财富股吧", "https://so.eastmoney.com/news/s?keyword={q}"),
        ("sina", "📰 新浪财经", "https://search.sina.com.cn/?q={q}&c=news&sort=time"),
        ("10jqka", "🔷 同花顺", "https://search.10jqka.com.cn/search?query={q}"),
        ("google", "🌐 Google", "https://www.google.com/search?q={q}+stock"),
        ("baidu", "🦋 百度", "https://www.baidu.com/s?wd={q}+股票"),
        ("biying", "💡 必应", "https://www.bing.com/search?q={q}+stock"),
        ("tgb", "📯 淘股吧", "https://www.tgb.cn/search?keyword={q}"),
        ("jiuyan", "🧭 韭研公社", "https://www.jiuyangongshe.com/search?q={q}"),
    ]

    # 🆕 社区热榜快捷链接
    _COMMUNITY_HOT_LINKS = [
        ("📱 雪球热帖榜", "https://xueqiu.com/hq"),
        ("💬 知乎热榜", "https://www.zhihu.com/hot"),
        ("📊 东方财富人气榜", "https://data.eastmoney.com/stockrank/hot.html"),
        ("📈 淘股吧精华", "https://www.tgb.cn/jinghua/"),
        ("🧭 韭研公社热门", "https://www.jiuyangongshe.com/"),
        ("🎪 微博热搜", "https://s.weibo.com/top/summary"),
        ("📰 财联社电报", "https://www.cls.cn/telegraph"),
        ("🏛️ 华尔街见闻", "https://wallstreetcn.com/live/global"),
    ]
    _SEARCH_STOCK_TEMPLATES = [
        "市值超500亿的白酒行业股票",
        "市盈率低于20倍的新能源股票",
        "半导体行业今日涨幅前10",
        "市值前20的银行股",
        "ROE连续3年超15%的消费龙头",
    ]
    _MACRO_TEMPLATES = [
        "2024年GDP增速、CPI年度值",
        "PMI制造业近6个月",
        "LPR1年期和5年期最新值",
        "社融存量同比增速月度",
        "进出口贸易额季度数据",
    ]

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

        # 右列-上: 大盘指数卡片 (🆕 整行可点击联动)
        _idx_frame = tk.LabelFrame(_right, text="📊 大盘指数",
                                    font=("TkDefaultFont", 11, "bold"))
        _idx_frame.pack(fill=tk.X, padx=4, pady=4)
        self._ifind_idx_labels = {}
        self._ifind_idx_rows = []  # 🆕 保存 (frame, code, name) 供点击绑定
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
            # 🆕 所有子控件都绑定点击 → 联动中列表格
            self._ifind_idx_rows.append((_row, _code, _name))
            for _w in (_row, _price_lbl, _pct_lbl, _nums_lbl,
                       *_row.winfo_children()):
                try:
                    _w.bind("<Button-1>",
                            lambda e, c=_code, n=_name: self._on_ifind_idx_click(c, n))
                    _w.configure(cursor="hand2")
                except Exception:
                    pass

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

        # 右列-下: 热点资讯 (🆕 支持点击打开链接)
        _news_frame = tk.LabelFrame(_right, text="📰 热点资讯 Top 5",
                                      font=("TkDefaultFont", 11, "bold"))
        _news_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._ifind_news_text = tk.Text(_news_frame, height=8, wrap=tk.WORD,
                                        font=("TkDefaultFont", 10),
                                        background="#fafafa", borderwidth=0,
                                        cursor="hand2")
        self._ifind_news_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._ifind_news_text.configure(state=tk.DISABLED)
        self._ifind_news_items_cache = []  # 🆕 缓存 items 供点击时取 URL

        # 🆕 热点资讯点击 → 打开链接
        self._ifind_news_text.bind("<Button-1>", self._on_ifind_news_text_click)

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
            self._ifind_news_items_cache = items[:5]  # 🆕 缓存
            self._ifind_news_text.configure(state=tk.NORMAL)
            self._ifind_news_text.delete("1.0", tk.END)
            for i, it in enumerate(items[:5], 1):
                _title = it.get("资讯标题", "?")
                _src = it.get("信息来源", "")
                _hot = it.get("资讯热度", "")
                # 🆕 title tag 绑定 clickable
                _tag = f"news_{i}"
                self._ifind_news_text.insert(tk.END, f"{i}. {_title}\n", _tag)
                self._ifind_news_text.insert(
                    tk.END, f"   来源:{_src}  热度:{_hot}\n\n")
                self._ifind_news_text.tag_configure(_tag,
                    font=("TkDefaultFont", 10, "bold", "underline"),
                    foreground="#1565C0")
                self._ifind_news_text.tag_bind(_tag, "<Button-1>",
                    lambda e, ii=i-1: self._on_ifind_news_item_click(ii))
            self._ifind_news_text.configure(state=tk.DISABLED)

        self._ifind_status.set("✅ 数据已更新")

    # ── 左列选中联动: 取数 + 渲染表格 ──
    def _ifind_on_feat_select(self, dlg):
        _sel = self._ifind_feat_lb.curselection()
        if not _sel:
            return
        _idx = _sel[0]
        _key, _label, _handler = self._IFIND_FEATURES[_idx]

        # 🆕 需要用户输入 query 的类型: 弹出简化输入对话框
        _QUERY_FEATURES = {"search", "search_stock", "summary", "macro", "macro_search", "notice"}
        _NEEDS_INPUT = _key in _QUERY_FEATURES

        # 🆕 弹窗类型: 不调用 iFinD API, 而是弹出独立对话框
        _DIALOG_FEATURES = {"multi_search", "community_hot"}
        _IS_DIALOG = _key in _DIALOG_FEATURES

        if _IS_DIALOG:
            # 🆕 多引擎搜索 / 社区热榜 — 直接弹独立对话框
            self._ifind_clear_mid()
            if _key == "multi_search":
                self._feat_multi_search_dialog()
            elif _key == "community_hot":
                self._feat_community_hot_dialog()
            self._ifind_status.set(f"✅ {_label} 已打开")
            return

        if _NEEDS_INPUT:
            q = self._ifind_prompt_query(_key, _label)
            if not q:
                self._ifind_status.set("⚠️ 已取消")
                return

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
                elif _key == "notice":
                    r = search_notice(q, size=15)
                elif _key == "search_stock":
                    r = search_securities(q)
                elif _key == "summary":
                    r = get_stock_summary(q)
                elif _key == "macro":
                    r = fetch_edb(q)
                elif _key == "macro_search":
                    r = search_edb(q)
                elif _key == "search":
                    r = _search_news_mcp(q, size=15)
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            self.root.after(0, lambda: self._ifind_render_mid(_key, _label, r))

        threading.Thread(target=_bg, daemon=True).start()

    # 🆕 简化 query 输入对话框 (模板按钮 + 自由输入)
    def _ifind_prompt_query(self, key, label):
        """弹出查询输入框, 支持模板快捷填充"""
        dlg = tk.Toplevel(self.root)
        dlg.title(f"🔍 {label} — 输入查询条件")
        dlg.geometry("520x280")
        dlg.transient(self.root)
        dlg.grab_set()

        result = {"query": None}

        tk.Label(dlg, text=f"请输入自然语言查询 (iFinD AI 解析):",
                 font=("", 11, "bold")).pack(anchor="w", padx=16, pady=(14, 6))

        # 模板按钮 (根据 key 显示不同模板)
        templates = []
        if key == "search_stock": templates = self._SEARCH_STOCK_TEMPLATES
        elif key == "macro" or key == "macro_search": templates = self._MACRO_TEMPLATES
        elif key == "notice": templates = ["今日A股重要公告", "贵州茅台最近公告", "重大重组公告"]
        elif key == "summary": templates = ["贵州茅台财务状况、估值、股东", "比亚迪基本面分析", "宁德时代行业地位"]
        elif key == "search": templates = ["A股今日利好消息", "人工智能行业动态", "新能源汽车销量"]

        if templates:
            tframe = tk.LabelFrame(dlg, text="💡 快捷模板", font=("", 10))
            tframe.pack(fill=tk.X, padx=16, pady=4)
            for t in templates:
                btn = tk.Button(tframe, text=t, cursor="hand2", relief=tk.FLAT,
                                fg="#1565C0", font=("", 10), anchor="w", pady=2,
                                command=lambda tt=t: (ent.delete(0, tk.END), ent.insert(0, tt)))
                btn.pack(anchor="w", padx=10)

        ent = ttk.Entry(dlg, font=("", 11))
        ent.pack(fill=tk.X, padx=16, pady=6)

        def _ok():
            result["query"] = ent.get().strip()
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=16, pady=6)
        ttk.Button(btn_frame, text="✅ 查询", command=_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="❌ 取消", command=dlg.destroy).pack(side=tk.RIGHT)

        dlg.wait_window()
        return result["query"]

    # ═══════════════════════════════════════════════════════════
    # 🆕 多引擎搜索聚合弹窗
    # ═══════════════════════════════════════════════════════════
    def _feat_multi_search_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🧠 AI 多引擎搜索聚合")
        dlg.geometry("680x560")
        dlg.transient(self.root)

        # 顶部输入区
        top = ttk.Frame(dlg)
        top.pack(fill=tk.X, padx=14, pady=(14, 8))

        ttk.Label(top, text="🔎 搜索关键词:", font=("", 11, "bold")).pack(side=tk.LEFT)
        ent = ttk.Entry(top, font=("", 12), width=40)
        ent.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        ent.focus_set()

        # 快捷模板
        tpl_frame = tk.LabelFrame(dlg, text="💡 快捷模板", font=("", 10))
        tpl_frame.pack(fill=tk.X, padx=14, pady=4)
        _templates = [
            "贵州茅台 估值分析",
            "比亚迪 近期研报",
            "半导体板块 后市展望",
            "美联储加息 A股影响",
            "北向资金 今日动向",
        ]
        for t in _templates:
            tk.Button(tpl_frame, text=t, cursor="hand2", relief=tk.FLAT,
                      fg="#1565C0", font=("", 10), anchor="w", pady=1,
                      command=lambda tt=t: (ent.delete(0, tk.END), ent.insert(0, tt))).pack(anchor="w", padx=8)

        # 引擎选择区 (不用 Canvas 滚动, 11 个够用直接平铺)
        eng_frame = tk.LabelFrame(dlg, text="🌐 搜索站点 (勾选后一键打开浏览器)", font=("", 10))
        eng_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        inner = ttk.Frame(eng_frame)
        inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 所有引擎默认勾选, 分 2 列显示
        check_vars = {}
        row = 0
        for i, (key, label, url_tpl) in enumerate(self._MULTI_SEARCH_ENGINES):
            v = tk.BooleanVar(value=True)
            check_vars[key] = (v, label, url_tpl)
            cb = ttk.Checkbutton(inner, text=label, variable=v, font=("", 10))
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=8, pady=2)
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)

        # 按钮区
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=14, pady=8)

        def _select_all(v=True):
            for k, (var, _, _) in check_vars.items():
                var.set(v)

        ttk.Button(btn_frame, text="全选", command=lambda: _select_all(True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="全不选", command=lambda: _select_all(False)).pack(side=tk.LEFT, padx=2)

        import urllib.parse, webbrowser

        def _open_all():
            q = ent.get().strip()
            if not q:
                ent.focus_set()
                return
            q_enc = urllib.parse.quote(q)
            opened = 0
            for key, (var, label, url_tpl) in check_vars.items():
                if var.get():
                    url = url_tpl.format(q=q_enc)
                    webbrowser.open_new_tab(url)
                    opened += 1
            status_lbl.config(text=f"✅ 已在 {opened} 个站点打开搜索: 「{q}」", foreground="#2e7d32")

        def _open_single(label, url_tpl):
            q = ent.get().strip()
            if not q:
                ent.focus_set()
                return
            url = url_tpl.format(q=urllib.parse.quote(q))
            webbrowser.open_new_tab(url)

        ttk.Button(btn_frame, text="🚀 一键搜索 (勾选的全部站点)",
                   command=_open_all).pack(side=tk.RIGHT, padx=4)

        # 单独快速按钮行
        quick_frame = ttk.Frame(dlg)
        quick_frame.pack(fill=tk.X, padx=14, pady=(0, 8))
        for key, label, url_tpl in self._MULTI_SEARCH_ENGINES[:5]:
            btn = tk.Button(quick_frame, text=label, cursor="hand2", relief=tk.FLAT,
                            fg="#1565C0", font=("", 10), anchor="w",
                            command=lambda l=label, u=url_tpl: _open_single(l, u))
            btn.pack(side=tk.LEFT, padx=3)

        status_lbl = ttk.Label(dlg, text="💡 输入关键词 → 勾选站点 → 一键同时打开所有搜索页",
                               foreground="#666")
        status_lbl.pack(fill=tk.X, padx=14, pady=(0, 10))

        # Enter 触发
        ent.bind("<Return>", lambda e: _open_all())

    # ═══════════════════════════════════════════════════════════
    # 🆕 社区热榜快捷导航弹窗
    # ═══════════════════════════════════════════════════════════
    def _feat_community_hot_dialog(self):
        import webbrowser

        dlg = tk.Toplevel(self.root)
        dlg.title("📺 社区热榜 + 资讯导航")
        dlg.geometry("520x480")
        dlg.transient(self.root)

        ttk.Label(dlg, text="🔥 热门社区 & 资讯网站",
                  font=("", 13, "bold")).pack(pady=(14, 4))

        ttk.Label(dlg, text="点击任一按钮 → 浏览器打开对应热榜 / 精华帖 / 实时电报",
                  foreground="#666", font=("", 9)).pack()

        # 快速一键: 打开全部 (前4个)
        def _open_all():
            for label, url in self._COMMUNITY_HOT_LINKS[:4]:
                webbrowser.open_new_tab(url)

        ttk.Button(dlg, text="🚀 一键打开前 4 个热门",
                   command=_open_all).pack(pady=8)

        # 按钮网格
        grid = ttk.Frame(dlg)
        grid.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        row = 0; col = 0
        for label, url in self._COMMUNITY_HOT_LINKS:
            btn = tk.Button(grid, text=label, cursor="hand2",
                            font=("", 11), padx=12, pady=8,
                            relief=tk.RAISED, bd=1,
                            command=lambda u=url: webbrowser.open_new_tab(u))
            btn.grid(row=row, column=col, padx=6, pady=6, sticky="we")
            col += 1
            if col >= 2:
                col = 0
                row += 1

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        ttk.Label(dlg, text="💡 所有链接在浏览器新标签页打开",
                  foreground="#999", font=("", 9)).pack(pady=(0, 10))

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
        try: self._apply_hyperlinks_to_text_widget(_txt)
        except Exception: pass
        _txt.configure(state=tk.DISABLED)

    def _ifind_render_mid(self, key, label, r):
        self._ifind_clear_mid()

        if not r.get("ok"):
            self._ifind_show_mid_text(
                f"❌ 加载失败: {label}\n\n错误: {r.get('error', '未知错误')}")
            self._ifind_status.set(f"❌ {label} 加载失败")
            return

        data = r.get("data", {})
        # iFinD data 有时是 dict {"data": {...}}, 有时直接是 dict, 有时是 str(md)
        d2 = data.get("data", data) if isinstance(data, dict) else data

        # news / notice 类型 (有列表结构)
        if key in ("news", "notice", "search"):
            items = []
            if isinstance(d2, dict):
                items = d2.get("result", d2.get("data", [])) or []
            elif isinstance(d2, list):
                items = d2
            self._ifind_render_news_table(items)
            self._ifind_status.set(f"✅ {label}: {len(items)} 条")
            return

        # macro_search / summary / macro 等返回 markdown table (answer 字段)
        md_text = None
        if isinstance(d2, dict):
            md_text = d2.get("answer", d2.get("data", None))
        elif isinstance(d2, str):
            md_text = d2

        headers, rows = ([], [])
        if isinstance(md_text, str) and "|" in md_text:
            # 先检查是否是 JSON 数组字符串 (比如 search_notice 返回)
            _stripped = md_text.strip()
            if (_stripped.startswith("[") and _stripped.endswith("]")) or (
                _stripped.startswith("{") and _stripped.endswith("}")):
                try:
                    _j = json.loads(_stripped)
                    if isinstance(_j, list):
                        items = _j
                        self._ifind_render_news_table(items)
                        self._ifind_status.set(f"✅ {label}: {len(items)} 条")
                        return
                except Exception: pass
            headers, rows = parse_markdown_table(md_text)

        if headers:
            self._ifind_render_data_table(headers, rows, key)
            self._ifind_status.set(f"✅ {label}: {len(rows)} 条")
            return

        # 最后 fallback: 标准 tables 格式 (security_highfreq_quotes 等)
        header2, rows2 = parse_tables(r.get("data", {}))
        if header2:
            self._ifind_render_data_table(header2, rows2, key)
            self._ifind_status.set(f"✅ {label}: {len(rows2)} 条")
            return

        # 都没有 → 显示原始文本
        display_text = md_text if isinstance(md_text, str) else (
            d2 if isinstance(d2, str) else json.dumps(d2, ensure_ascii=False)[:2000])
        self._ifind_show_mid_text(
            f"📋 {label}\n\n{display_text}\n\n---数据来源: 同花顺 iFinD---")
        self._ifind_status.set(f"✅ {label}: 文本格式")

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

        # 🆕 自适应列名: 不同接口列名不同 (公告标题 / 资讯标题 / 信息来源 / URL 等)
        _first = items[0] if items and isinstance(items[0], dict) else {}
        _has_notice = any("公告" in str(k) for k in _first.keys())

        tree = ttk.Treeview(self._ifind_tree_frame,
                            columns=("title", "source", "date", "content"),
                            show="headings", height=min(15, len(items)))
        tree.heading("title", text="📰 标题")
        tree.heading("source", text="来源")
        tree.heading("date", text="日期")
        tree.heading("content", text="摘要")
        tree.column("title", width=320, anchor="w")
        tree.column("source", width=80, anchor="center")
        tree.column("date", width=90, anchor="center")
        tree.column("content", width=400, anchor="w")

        for it in items:
            if not isinstance(it, dict): continue
            # 🆕 兼容多种列名
            _title = it.get("公告标题", "") or it.get("资讯标题", "") or it.get("标题", "")
            _src = it.get("信息来源", "") or it.get("来源", "") or it.get("公告类型", "")
            _date = it.get("日期", "") or it.get("发布时间", "") or it.get("时间", "")
            _cont = (it.get("资讯内容") or it.get("公告片段内容") or it.get("内容") or "")[:120] + "..."
            tree.insert("", tk.END, values=(_title, _src, _date, _cont))

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
        """中列表格双击股票 → 后台拉K线 + 弹窗显示 (用 identify_row 代替 selection)"""
        tree = event.widget
        # 🆕 关键修复: identify_row 精确命中双击的行, 避免 selection() 总是返回上一个选中的
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        vals = tree.item(row_id, "values")
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
        # 🆕 关键修复: identify_row + identify_column 精确定位
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        idx = tree.index(row_id)
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

    # ══════════════════════════════════════════════════
    # 🆕 右列-大盘指数 点击联动
    # ══════════════════════════════════════════════════

    def _on_ifind_idx_click(self, ts_code, sname):
        """点击右列指数卡片 → 左列自动选📊大盘指数 → 中列表格自动定位该行 → 可选双击联动K线"""
        # 1. 左列选中 "大盘指数实时"
        for i, (k, l, _) in enumerate(self._IFIND_FEATURES):
            if k == "index":
                self._ifind_feat_lb.selection_clear(0, tk.END)
                self._ifind_feat_lb.selection_set(i)
                self._ifind_feat_lb.see(i)
                break
        else:
            return

        # 2. 触发左列选中回调 (加载指数数据)
        self._ifind_on_feat_select(self._ifind_feat_lb.winfo_toplevel())

        # 3. 等数据渲染完成后, 在中列表格里定位 + 高亮
        def _after_render():
            tree = getattr(self, "_ifind_tree", None)
            if not tree:
                return
            children = tree.get_children()
            for ch in children:
                vals = tree.item(ch, "values")
                if vals and str(vals[0]).strip() == ts_code:
                    # 选中 + 滚动到可见
                    tree.selection_set(ch)
                    tree.see(ch)
                    tree.focus(ch)
                    tree.activate(ch)
                    # 闪烁高亮一下
                    try:
                        tree.tag_configure("_flash", background="#e3f2fd")
                        tree.item(ch, tags=("_flash",))
                        tree.after(500, lambda: tree.item(ch, tags=()))
                    except Exception:
                        pass
                    break
            self._ifind_status.set(f"✅ 已定位到 {sname}")

        self._ifind_tree_frame.after(800, _after_render)

    # ══════════════════════════════════════════════════
    # 🆕 右列-热点资讯 点击 (Text tag 绑定 + 兜底)
    # ══════════════════════════════════════════════════

    def _on_ifind_news_item_click(self, idx):
        """Text tag 绑定的点击 → 打开对应 URL"""
        items = getattr(self, "_ifind_news_items_cache", [])
        if 0 <= idx < len(items):
            url = (items[idx].get("URL") or items[idx].get("url") or "").strip()
            if url:
                self._open_url_reliable(url)
            else:
                self._ifind_status.set("⚠️ 此条资讯无原文链接")

    def _on_ifind_news_text_click(self, event):
        """Text 点击兜底: 没点中 tag 时, 按行号取 cache"""
        text = event.widget
        pos = text.index(f"@{event.x},{event.y}")
        line_num = int(pos.split(".")[0])
        # Text 里每行是 "N. title" + "   来源..." + 空行 → 每 3 行一条
        idx = (line_num - 1) // 3
        self._on_ifind_news_item_click(idx)

    def _open_url_reliable(self, url):
        """统一的 URL 打开 (webbrowser + macOS `open` 兜底)"""
        import webbrowser, subprocess
        try:
            if not webbrowser.open_new_tab(url):
                subprocess.Popen(["open", url])
        except Exception:
            try:
                subprocess.Popen(["open", url])
            except Exception:
                self._ifind_status.set(f"❌ 打开链接失败: {url[:60]}")
                return
        self._ifind_status.set("✅ 已在浏览器中打开")


