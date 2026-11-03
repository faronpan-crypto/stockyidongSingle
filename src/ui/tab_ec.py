# ═══════════════════════════════════════════════════════════════
# 📅 财经日历弹窗 (EventCalendarMixin)
# 三列 PanedWindow:
#   左列: 财经日历事件 (Treeview)
#   中列: 选中事件 → 关联股票 (Treeview, 双击K线)
#   右列: 中列选中股票 → 日K线 + 一目均衡 + 附图 + 综合 (Notebook 4 tab)
# ═══════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import ttk
import threading
import datetime as _dt
import os as _os_ec
import webbrowser as _wb_ec


# ═══════════════════════════════════════════════════════════════
# 🔥 内置财经日历事件库 (按影响板块分类)
# ═══════════════════════════════════════════════════════════════

# 板块 → 可能受影响的股票关键词 (用于匹配关联个股)
_SECTOR_KEYWORDS = {
    "央行利率决议": ["银行", "保险", "券商", "房地产", "白酒", "消费"],
    "美联储议息": ["黄金", "有色", "银行", "出口", "电子"],
    "CPI 发布": ["消费", "食品", "白酒", "猪肉", "农业"],
    "PPI 发布": ["工业", "有色", "钢铁", "煤炭", "化工"],
    "GDP 发布": ["基建", "建材", "工程机械", "银行"],
    "PMI 发布": ["制造业", "工业", "物流", "原材料"],
    "非农数据": ["黄金", "有色", "半导体", "出口"],
    "LPR 报价": ["银行", "保险", "房地产"],
    "社融数据": ["银行", "券商", "保险", "基建"],
    "进出口数据": ["港口", "航运", "出口", "纺织"],
    "FOMC 会议": ["黄金", "有色", "半导体", "电子"],
    "原油库存": ["石油", "化工", "能源"],
    "OPEC 会议": ["石油", "化工", "能源"],
    "美债收益率": ["黄金", "银行", "保险"],
    "日元汇率": ["出口", "电子", "汽车"],
    "人民币汇率": ["出口", "纺织", "航空"],
}

# 预设的未来事件 (按日期排序, 重要度: ⭐~⭐⭐⭐)
_TODAY = _dt.date.today()

def _build_default_events():
    """生成默认财经日历事件 (当前月 + 下月)"""
    events = []
    m = _TODAY.month
    y = _TODAY.year

    # ── 宏观数据发布日 (固定) ──
    _MACRO_DATES = [
        ("每月10日前后", "CPI 发布", "中国", "每月固定"),
        ("每月15日前后", "社融数据", "中国", "每月固定"),
        ("每月中旬", "LPR 报价", "中国", "每月20日"),
        ("每月20日前后", "PPI 发布", "中国", "每月固定"),
        ("每月最后一周", "PMI 发布", "中国", "每月固定"),
        ("每月第一个周五", "非农数据", "美国", "每月固定"),
        ("每月中旬", "美联储议息", "美国", "FOMC"),
        ("每季度末", "GDP 发布", "多国", "季度"),
    ]

    for desc, name, country, period in _MACRO_DATES:
        events.append({
            "name": name, "date": f"{y}-{m:02d}", "country": country,
            "importance": "⭐⭐⭐", "sector": name.split()[0] if " " in name else name,
            "period": period, "desc": f"{desc}发布{name}",
        })

    # ── 近期重要事件 ──
    _NEAR_TERM = [
        ("2026-11-03", "美联储FOMC会议决议", "美国", "⭐⭐⭐", "FOMC/议息", "2026年11月美联储议息会议,影响全球流动性"),
        ("2026-11-05", "中国10月CPI数据", "中国", "⭐⭐⭐", "CPI/通胀", "10月CPI同比预期,影响货币政策走向"),
        ("2026-11-06", "中国10月进出口数据", "中国", "⭐⭐", "进出口/外贸", "出口增速反映外需情况"),
        ("2026-11-07", "美国10月非农数据", "美国", "⭐⭐⭐", "非农/就业", "非农就业人数变化,影响美联储利率决议"),
        ("2026-11-10", "中国10月PPI数据", "中国", "⭐⭐", "PPI/工业", "工业品出厂价格同比,反映工业景气度"),
        ("2026-11-11", "双11购物节", "中国", "⭐⭐", "消费/电商", "年度消费旺季,利好电商平台和物流"),
        ("2026-11-13", "中国10月社融数据", "中国", "⭐⭐⭐", "社融/金融", "社会融资规模,反映实体经济融资需求"),
        ("2026-11-15", "MLF/LPR报价日", "中国", "⭐⭐⭐", "LPR/利率", "中期借贷便利操作利率,影响银行报价"),
        ("2026-11-20", "OPEC+会议", "国际", "⭐⭐", "OPEC/原油", "石油输出国组织产量决议,影响油价"),
        ("2026-11-25", "中国11月PMI预览", "中国", "⭐⭐⭐", "PMI/制造", "制造业PMI初值,反映经济景气"),
        ("2026-12-15", "美联储FOMC会议", "美国", "⭐⭐⭐", "FOMC/议息", "12月美联储议息会议,大概率降息25bp"),
        ("2026-12-25", "圣诞假期", "全球", "⭐", "假期", "欧美市场休市"),
    ]

    for date, name, country, imp, sector, desc in _NEAR_TERM:
        events.append({
            "name": name, "date": date, "country": country,
            "importance": imp, "sector": sector, "period": "", "desc": desc,
        })

    return sorted(events, key=lambda x: x["date"])


# ═══════════════════════════════════════════════════════════════
# 🔥 关键板块 → 可能受影响股票池 (关键词匹配用)
# ═══════════════════════════════════════════════════════════════

_SECTOR_STOCK_MAP = {
    # 央行利率 → 银行/保险/地产/白酒
    "利率": [
        ("601398.SH", "工商银行"), ("601288.SH", "农业银行"),
        ("600036.SH", "招商银行"), ("601318.SH", "中国平安"),
        ("600030.SH", "中信证券"), ("600999.SH", "招商证券"),
        ("000002.SZ", "万科A"), ("600048.SH", "保利发展"),
        ("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液"),
    ],
    "CPI": [
        ("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液"),
        ("600809.SH", "山西汾酒"), ("000568.SZ", "泸州老窖"),
        ("002714.SZ", "牧原股份"), ("000876.SZ", "新 希 望"),
        ("002458.SZ", "益生股份"), ("603345.SH", "安井食品"),
    ],
    "PPI": [
        ("601899.SH", "紫金矿业"), ("000878.SZ", "云南铜业"),
        ("601600.SH", "中国铝业"), ("002493.SZ", "荣盛石化"),
        ("601857.SH", "中国石油"), ("600028.SH", "中国石化"),
        ("000708.SZ", "中信特钢"), ("002318.SZ", "久立特材"),
    ],
    "FOMC": [
        ("601899.SH", "紫金矿业"), ("002155.SZ", "湖南黄金"),
        ("600547.SH", "山东黄金"), ("600036.SH", "招商银行"),
        ("601318.SH", "中国平安"), ("002475.SZ", "立讯精密"),
        ("300750.SZ", "宁德时代"), ("601012.SH", "隆基绿能"),
    ],
    "非农": [
        ("601899.SH", "紫金矿业"), ("002155.SZ", "湖南黄金"),
        ("600547.SH", "山东黄金"), ("300750.SZ", "宁德时代"),
        ("002475.SZ", "立讯精密"), ("002241.SZ", "歌尔股份"),
    ],
    "PMI": [
        ("601100.SH", "恒立液压"), ("002422.SZ", "科伦药业"),
        ("300274.SZ", "阳光电源"), ("600031.SH", "三一重工"),
        ("600741.SH", "华域汽车"), ("000333.SZ", "美的集团"),
    ],
    "进出口": [
        ("601872.SH", "招商轮船"), ("601919.SH", "中远海控"),
        ("600018.SH", "上港集团"), ("002054.SZ", "德美化工"),
        ("002493.SZ", "荣盛石化"), ("600227.SH", "赤天化"),
    ],
    "社融": [
        ("601398.SH", "工商银行"), ("600036.SH", "招商银行"),
        ("600030.SH", "中信证券"), ("601688.SH", "华泰证券"),
        ("601318.SH", "中国平安"), ("600816.SH", "安信信托"),
    ],
    "LPR": [
        ("601398.SH", "工商银行"), ("600036.SH", "招商银行"),
        ("601318.SH", "中国平安"), ("600048.SH", "保利发展"),
        ("000002.SZ", "万科A"), ("600115.SH", "东方航空"),
    ],
    "OPEC": [
        ("601857.SH", "中国石油"), ("600028.SH", "中国石化"),
        ("601808.SH", "中海油服"), ("600688.SH", "上海石化"),
        ("002493.SZ", "荣盛石化"), ("600803.SH", "新奥股份"),
    ],
    "消费": [
        ("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液"),
        ("603288.SH", "海天味业"), ("300015.SZ", "爱尔眼科"),
        ("600887.SH", "伊利股份"), ("000333.SZ", "美的集团"),
        ("300750.SZ", "宁德时代"), ("002415.SZ", "海康威视"),
    ],
}


class EventCalendarMixin:
    """📅 财经日历弹窗 Mixin"""

    # ── 左列事件表头 ──
    _EC_LEFT_HEADER = ["日期", "时间", "国家/地区", "事件名称", "重要度", "影响板块"]
    _EC_LEFT_WIDTHS = [100, 80, 80, 220, 70, 120]

    # ── 中列股票表头 ──
    _EC_MID_HEADER = ["证券代码", "证券简称", "关联原因", "影响方向", "热度"]

    def _show_event_calendar_dialog(self):
        """📅 财经日历弹窗主入口"""
        dlg = tk.Toplevel(self.root)
        dlg.title("📅 财经日历 - 宏观事件与市场影响")
        dlg.geometry("1280x720")
        dlg.transient(self.root)
        try:
            dlg.grab_set()
        except Exception:
            pass

        # ═══ 顶部工具栏 ═══
        _top = ttk.Frame(dlg)
        _top.pack(fill=tk.X, padx=6, pady=4)

        ttk.Button(_top, text="📅 刷新日历",
                   command=lambda: self._ec_refresh_events()).pack(side=tk.LEFT, padx=2)
        ttk.Button(_top, text="📊 仅看今日",
                   command=lambda: self._ec_filter_today()).pack(side=tk.LEFT, padx=2)
        ttk.Button(_top, text="🔥 仅看⭐⭐⭐",
                   command=lambda: self._ec_filter_important()).pack(side=tk.LEFT, padx=2)
        ttk.Button(_top, text="📈 全部",
                   command=lambda: self._ec_filter_all()).pack(side=tk.LEFT, padx=2)

        # 快速日期跳转
        ttk.Label(_top, text="  跳转:").pack(side=tk.LEFT, padx=(10, 2))
        self._ec_date_var = tk.StringVar(value=_TODAY.strftime("%Y-%m-%d"))
        ttk.Entry(_top, textvariable=self._ec_date_var, width=12).pack(side=tk.LEFT)
        ttk.Button(_top, text="📌 定位",
                   command=lambda: self._ec_goto_date()).pack(side=tk.LEFT, padx=2)

        self._ec_status = tk.StringVar(value="⏳ 加载财经日历...")
        ttk.Label(_top, textvariable=self._ec_status,
                  foreground="#666").pack(side=tk.RIGHT, padx=6)

        # ═══ 三列 PanedWindow ═══
        _pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        _pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── 左列: 财经日历事件 ──
        _left = ttk.Frame(_pw, width=350)
        _pw.add(_left, weight=2)

        ttk.Label(_left, text="📅 财经日历事件",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=4, pady=2)

        _lf = ttk.Frame(_left)
        _lf.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._ec_events = _build_default_events()
        self._ec_all_events = list(self._ec_events)  # 保留完整列表供 filter

        self._ec_left_tree = ttk.Treeview(
            _lf, columns=self._EC_LEFT_HEADER, show="headings", height=20)
        for i, (h, w) in enumerate(zip(self._EC_LEFT_HEADER, self._EC_LEFT_WIDTHS)):
            self._ec_left_tree.heading(h, text=h)
            self._ec_left_tree.column(h, width=w, anchor="w")
        _lvsb = ttk.Scrollbar(_lf, orient=tk.VERTICAL,
                              command=self._ec_left_tree.yview)
        self._ec_left_tree.configure(yscrollcommand=_lvsb.set)
        self._ec_left_tree.grid(row=0, column=0, sticky="nsew")
        _lvsb.grid(row=0, column=1, sticky="ns")
        _lf.rowconfigure(0, weight=1)
        _lf.columnconfigure(0, weight=1)

        # 左列行着色 (重要度)
        self._ec_left_tree.tag_configure("star3", background="#fff3e0")  # ⭐⭐⭐ 橙色底
        self._ec_left_tree.tag_configure("star2", background="#fffde7")  # ⭐⭐ 黄色底
        self._ec_left_tree.tag_configure("past", foreground="#aaa")       # 已过去灰色

        # 左列选中 → 中列联动
        self._ec_left_tree.bind("<<TreeviewSelect>>",
                                lambda e: self._ec_on_left_select())

        # ── 中列: 关联股票 ──
        _mid = ttk.Frame(_pw, width=380)
        _pw.add(_mid, weight=3)

        ttk.Label(_mid, text="🎯 可能受影响的股票",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=4, pady=2)

        _mf = ttk.Frame(_mid)
        _mf.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._ec_mid_tree = ttk.Treeview(
            _mf, columns=self._EC_MID_HEADER, show="headings", height=20)
        for h, w in zip(self._EC_MID_HEADER, [110, 100, 150, 80, 60]):
            self._ec_mid_tree.heading(h, text=h)
            self._ec_mid_tree.column(h, width=w, anchor="w")
        _mvsb = ttk.Scrollbar(_mf, orient=tk.VERTICAL,
                              command=self._ec_mid_tree.yview)
        self._ec_mid_tree.configure(yscrollcommand=_mvsb.set)
        self._ec_mid_tree.grid(row=0, column=0, sticky="nsew")
        _mvsb.grid(row=0, column=1, sticky="ns")
        _mf.rowconfigure(0, weight=1)
        _mf.columnconfigure(0, weight=1)

        self._ec_mid_tree.tag_configure("rise", foreground="#d32f2f")
        self._ec_mid_tree.tag_configure("fall", foreground="#388e3c")

        # 中列选中 → 右列联动
        self._ec_mid_tree.bind("<<TreeviewSelect>>",
                               lambda e: self._ec_on_mid_select())
        # 中列双击 → 打开独立 K 线弹窗
        self._ec_mid_tree.bind("<Double-1>",
                               lambda e: self._ec_on_mid_double(e))

        # ── 右列: K 线 Notebook (复用打折促销的 4 tab) ──
        _right = ttk.Frame(_pw, width=550)
        _pw.add(_right, weight=5)

        self._ec_right_nb = ttk.Notebook(_right)
        self._ec_right_nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        _ph = tk.Label(self._ec_right_nb,
                       text="👈 左列选财经事件 → 中列自动推关联股票\n   中列选中 → 右列自动刷日K/一目均衡/附图/综合",
                       font=("Menlo", 12), bg="#F5F5F5", fg="#888", justify="center")
        self._ec_right_nb.add(_ph, text="📊 等待选择")

        # ── 底部: 事件详情 ──
        _detail = tk.LabelFrame(dlg, text="📋 事件详情",
                                font=("TkDefaultFont", 10, "bold"))
        _detail.pack(fill=tk.X, padx=4, pady=2)
        self._ec_detail_text = tk.Text(_detail, height=2, wrap=tk.WORD,
                                        font=("TkDefaultFont", 10),
                                        background="#fafafa", borderwidth=0)
        self._ec_detail_text.pack(fill=tk.X, padx=4, pady=2)
        self._ec_detail_text.configure(state=tk.DISABLED)

        # ── 初始渲染 ──
        self._ec_fill_left()
        self._ec_status.set(f"✅ 已加载 {len(self._ec_events)} 个财经事件")

    # ═══════════════════════════════════════════════════════════════
    # 左列: 填充 + 过滤
    # ═══════════════════════════════════════════════════════════════

    def _ec_fill_left(self):
        """用 self._ec_events 渲染左列 Treeview"""
        for iid in self._ec_left_tree.get_children():
            self._ec_left_tree.delete(iid)

        today_str = _TODAY.strftime("%Y-%m-%d")
        for i, ev in enumerate(self._ec_events):
            # 计算时间描述
            try:
                ev_date = _dt.datetime.strptime(ev["date"], "%Y-%m-%d").date()
                days = (ev_date - _TODAY).days
                if days < 0:
                    time_desc = "已过去"
                    tag = "past"
                elif days == 0:
                    time_desc = "⏰ 今日"
                    tag = "star" + str(ev["importance"].count("⭐"))
                elif days == 1:
                    time_desc = "明日"
                    tag = "star" + str(ev["importance"].count("⭐"))
                elif days <= 7:
                    time_desc = f"{days}天后"
                    tag = "star" + str(ev["importance"].count("⭐"))
                else:
                    time_desc = f"{days}天后"
                    tag = ""
            except Exception:
                time_desc = ""
                tag = ""

            row = (ev["date"], time_desc, ev["country"], ev["name"],
                   ev["importance"], ev["sector"])
            self._ec_left_tree.insert("", tk.END, values=row, tags=(tag,))

    def _ec_filter_today(self):
        today_str = _TODAY.strftime("%Y-%m-%d")
        self._ec_events = [e for e in self._ec_all_events
                           if e["date"] == today_str or "每月" in e.get("desc", "")]
        if not self._ec_events:
            self._ec_events = [e for e in self._ec_all_events
                               if _dt.datetime.strptime(e["date"], "%Y-%m-%d").date() >= _TODAY][:5]
        self._ec_fill_left()
        self._ec_status.set(f"📅 今日/近期事件 {len(self._ec_events)} 条")

    def _ec_filter_important(self):
        self._ec_events = [e for e in self._ec_all_events if "⭐⭐⭐" in e["importance"]]
        self._ec_fill_left()
        self._ec_status.set(f"⭐⭐⭐ 重要事件 {len(self._ec_events)} 条")

    def _ec_filter_all(self):
        self._ec_events = list(self._ec_all_events)
        self._ec_fill_left()
        self._ec_status.set(f"📅 全部 {len(self._ec_events)} 个财经事件")

    def _ec_goto_date(self):
        target = self._ec_date_var.get().strip()
        for i, ev in enumerate(self._ec_events):
            if ev["date"] == target:
                iid = self._ec_left_tree.get_children()[i]
                self._ec_left_tree.selection_set(iid)
                self._ec_left_tree.see(iid)
                self._ec_left_tree.focus(iid)
                self._ec_status.set(f"✅ 定位到 {target}")
                return
        self._ec_status.set(f"⚠️ {target} 未找到匹配事件")

    # ═══════════════════════════════════════════════════════════════
    # 联动: 左列选事件 → 中列关联股票
    # ═══════════════════════════════════════════════════════════════

    def _ec_on_left_select(self):
        """左列选中事件 → 中列自动推送关联股票"""
        sel = self._ec_left_tree.selection()
        if not sel:
            return
        idx = self._ec_left_tree.index(sel[0])
        if idx >= len(self._ec_events):
            return
        ev = self._ec_events[idx]
        self._ec_current_event = ev  # 🆕 保存当前事件供右列影响分析用

        # 显示事件详情
        self._ec_detail_text.configure(state=tk.NORMAL)
        self._ec_detail_text.delete("1.0", tk.END)
        self._ec_detail_text.insert(tk.END,
            f"📅 {ev['date']} | {ev['country']} | {ev['importance']} | {ev['name']}\n"
            f"   {ev['desc']}")
        self._ec_detail_text.configure(state=tk.DISABLED)

        # 匹配关联股票
        affected = self._ec_find_affected_stocks(ev)
        self._ec_fill_mid(affected, ev)

    def _ec_find_affected_stocks(self, event):
        """根据事件的 sector/name 匹配可能受影响的股票"""
        results = []
        sector = event.get("sector", "")

        # 1. 精确匹配 sector (key → 股票池)
        matched_keys = []
        for key in _SECTOR_STOCK_MAP:
            if key in sector or key in event.get("name", "") or key in event.get("desc", ""):
                matched_keys.append(key)

        # 2. 通用关键词匹配
        for key in _SECTOR_STOCK_MAP:
            for kw in _SECTOR_KEYWORDS.get(key, []):
                if kw in sector or kw in event.get("name", "") or kw in event.get("desc", ""):
                    if key not in matched_keys:
                        matched_keys.append(key)

        # 3. 默认: 消费类事件 → 消费板块
        if not matched_keys:
            if any(w in event.get("name", "") + event.get("sector", "")
                   for w in ["利率", "议息", "FOMC", "LPR", "央行"]):
                matched_keys = ["利率"]
            elif any(w in event.get("name", "") + event.get("sector", "")
                     for w in ["消费", "零售", "双11", "电商"]):
                matched_keys = ["消费"]
            elif any(w in event.get("name", "") + event.get("sector", "")
                     for w in ["Cpi", "CPI"]):
                matched_keys = ["CPI"]
            else:
                matched_keys = ["消费"]  # 兜底

        # 收集股票 + 去重
        seen = set()
        for key in matched_keys:
            for ts_code, sname in _SECTOR_STOCK_MAP.get(key, []):
                if ts_code not in seen:
                    seen.add(ts_code)
                    results.append({
                        "ts_code": ts_code,
                        "sname": sname,
                        "reason": key,
                        "direction": "↑ 利好" if self._ec_is_positive(
                            event, key) else "↓ 利空",
                        "heat": "🔥" if key in matched_keys[:2] else "",
                    })

        return results

    def _ec_is_positive(self, event, sector_key):
        """简单判断事件对板块是利好还是利空 (经验规则)"""
        name = event.get("name", "") + event.get("desc", "")
        # 利率决议: 降息→利好股市, 加息→利空
        if any(w in name for w in ["降息", "下调", "降准"]):
            return True
        if any(w in name for w in ["加息", "上调"]):
            return False
        # CPI/PPI: 温和通胀→利好消费, 超预期→利空
        if "CPI" in name or "cpi" in name or "通胀" in name:
            return True  # 默认温和通胀利好消费股
        # 非农: 超预期→美联储加息压力→利空黄金
        if "非农" in name and sector_key in ["FOMC", "利率"]:
            return False
        # 默认: 中性→按利好处理
        return True

    def _ec_fill_mid(self, stocks, event):
        """渲染中列关联股票表格"""
        for iid in self._ec_mid_tree.get_children():
            self._ec_mid_tree.delete(iid)

        for s in stocks:
            tag = "rise" if "↑" in s["direction"] else "fall"
            row = (s["ts_code"], s["sname"], s["reason"],
                   s["direction"], s["heat"])
            self._ec_mid_tree.insert("", tk.END, values=row, tags=(tag,))

        self._ec_mid_data = stocks  # 缓存, 供选中时用
        self._ec_status.set(
            f"🎯 {event.get('name', '')} → {len(stocks)} 只关联股票")

    # ═══════════════════════════════════════════════════════════════
    # 联动: 中列选中 → 右列信息+新闻+影响分析面板
    # ═══════════════════════════════════════════════════════════════

    def _ec_on_mid_select(self):
        """中列选中股票 → 右列显示信息+新闻+财经日历影响分析"""
        sel = self._ec_mid_tree.selection()
        if not sel:
            return
        idx = self._ec_mid_tree.index(sel[0])
        if not hasattr(self, "_ec_mid_data") or idx >= len(self._ec_mid_data):
            return

        s = self._ec_mid_data[idx]
        ts_code = s["ts_code"]
        sname = s["sname"]

        try:
            _base, _suf = ts_code.split(".", 1)
            sina_code = ("sh" if _suf.upper() == "SH" else
                         ("sz" if _suf.upper() == "SZ" else
                          ("bj" if _suf.upper() == "BJ" else ""))) + _base
        except Exception:
            return

        # 拿当前选中的财经事件名
        ev_name = ""
        try:
            ev_sel = self._ec_left_tree.selection()
            if ev_sel:
                ev_idx = self._ec_left_tree.index(ev_sel[0])
                if hasattr(self, "_ec_current_event"):
                    ev_name = getattr(self, "_ec_current_event", {}).get("name", "")
                elif ev_idx < len(self._ec_events):
                    ev_name = self._ec_events[ev_idx].get("name", "")
        except: pass

        self._ec_status.set(f"📋 {sname} 信息面板...")
        self._ec_build_right_info_panel(sina_code, sname, ev_name)

    def _ec_build_right_notebook(self, kdf, sname, Fig, FCA, np, gs):
        """构建右列 Notebook 4 tab (📈日K / 🌊一目 / 📊附图 / 📐综合) — 精简版"""
        # 清掉旧 tab
        for _t in self._ec_right_nb.tabs():
            self._ec_right_nb.forget(_t)

        if kdf is None or len(kdf) < 30:
            tk.Label(self._ec_right_nb,
                     text=f"{sname}\nK线数据不足(<30)",
                     font=("Menlo", 14), fg="#E53935").pack(expand=True)
            self._ec_right_nb.add(tk.Frame(self._ec_right_nb), text="📈 日K线")
            return

        # ── 提取 OHLCV ──
        closes = kdf["close"].values.astype(float)
        highs = kdf["high"].values.astype(float)
        lows = kdf["low"].values.astype(float)
        opens = kdf["open"].values.astype(float)
        volumes = kdf["volume"].values.astype(float)
        n = len(closes)
        x = np.arange(n)
        dates = kdf["date"].values if "date" in kdf.columns else np.arange(n)

        # 计算指标
        ma5 = np.convolve(closes, np.ones(5)/5, mode='valid')
        ma10 = np.convolve(closes, np.ones(10)/10, mode='valid')
        ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
        ma60 = np.convolve(closes, np.ones(60)/60, mode='valid')

        # ── Tab1: 📈 日K + MA ──
        t1 = tk.Frame(self._ec_right_nb)
        fig1 = Fig(figsize=(6, 4), dpi=100)
        ax1 = fig1.add_subplot(111)
        # 画 K 线 (简化版 bar)
        for i in range(n):
            color = "#d32f2f" if closes[i] >= opens[i] else "#388e3c"
            ax1.bar(x[i], closes[i] - opens[i], bottom=opens[i],
                    color=color, width=0.8)
            ax1.vlines(x[i], lows[i], highs[i], color=color, linewidth=0.5)
        # MA 均线
        if len(ma5) >= 1:
            ax1.plot(x[4:], ma5, label="MA5", color="#FF9800", linewidth=1)
        if len(ma10) >= 1:
            ax1.plot(x[9:], ma10, label="MA10", color="#2196F3", linewidth=1)
        if len(ma20) >= 1:
            ax1.plot(x[19:], ma20, label="MA20", color="#9C27B0", linewidth=1)
        if len(ma60) >= 1:
            ax1.plot(x[59:], ma60, label="MA60", color="#607D8B", linewidth=1)
        ax1.set_title(f"{sname} 日K线 ({n}根)", fontsize=11)
        ax1.legend(fontsize=8, loc="upper left")
        ax1.grid(True, alpha=0.3)
        fig1.tight_layout()
        FCA(fig1, t1).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._ec_right_nb.add(t1, text="📈 日K线")

        # ── Tab2: 🌊 一目均衡 ──
        t2 = tk.Frame(self._ec_right_nb)
        try:
            ich = self._calc_ichimoku(highs, lows, closes)
            fig2 = Fig(figsize=(6, 4), dpi=100)
            ax2 = fig2.add_subplot(111)
            # K 线
            for i in range(n):
                color = "#d32f2f" if closes[i] >= opens[i] else "#388e3c"
                ax2.bar(x[i], closes[i] - opens[i], bottom=opens[i],
                        color=color, width=0.8)
                ax2.vlines(x[i], lows[i], highs[i], color=color, linewidth=0.5)
            # 一目均衡 5 线
            ext_x = list(range(n + 26))
            ax2.plot(ext_x[:len(ich["tenkan"])], ich["tenkan"],
                     color="#FF9800", linewidth=1, label="转换线")
            ax2.plot(ext_x[:len(ich["kijun"])], ich["kijun"],
                     color="#2196F3", linewidth=1, label="基准线")
            ax2.plot(ext_x[:len(ich["senkou_a"])], ich["senkou_a"],
                     color="#9C27B0", linewidth=1, label="先行带A")
            ax2.plot(ext_x[:len(ich["senkou_b"])], ich["senkou_b"],
                     color="#607D8B", linewidth=1, label="先行带B")
            # 先行带填充
            ax2.fill_between(ext_x[:len(ich["senkou_a"])], ich["senkou_a"],
                             ich["senkou_b"], alpha=0.15, color="#9C27B0")
            # 迟行带
            if "chikou" in ich and len(ich["chikou"]) > 0:
                ax2.plot(ext_x[26:26+len(ich["chikou"])],
                         ich["chikou"], color="#4CAF50", linewidth=1,
                         label="迟行带")
            ax2.set_title(f"{sname} 一目均衡表", fontsize=11)
            ax2.legend(fontsize=8, loc="upper left")
            ax2.grid(True, alpha=0.3)
            fig2.tight_layout()
            FCA(fig2, t2).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as ex:
            tk.Label(t2, text=f"一目均衡计算失败: {ex}",
                     fg="#E53935").pack(expand=True)
        self._ec_right_nb.add(t2, text="🌊 一目均衡")

        # ── Tab3: 📊 附图指标 (MACD + RSI + KDJ) ──
        t3 = tk.Frame(self._ec_right_nb)
        fig3 = Fig(figsize=(6, 5), dpi=100)
        gs3 = gs.GridSpec(3, 1, height_ratios=[1, 1, 1], hspace=0.4)

        # MACD
        ax3a = fig3.add_subplot(gs3[0])
        ema12 = self._ec_ema(closes, 12)
        ema26 = self._ec_ema(closes, 26)
        dif = ema12 - ema26
        dea = self._ec_ema(dif, 9)
        macd_bar = (dif - dea) * 2
        ax3a.bar(x[-len(macd_bar):], macd_bar,
                 color=["#d32f2f" if v >= 0 else "#388e3c" for v in macd_bar])
        ax3a.plot(x[-len(dif):], dif, color="#2196F3", linewidth=1, label="DIF")
        ax3a.plot(x[-len(dea):], dea, color="#FF9800", linewidth=1, label="DEA")
        ax3a.set_title("MACD", fontsize=10)
        ax3a.legend(fontsize=7)
        ax3a.grid(True, alpha=0.3)

        # RSI
        ax3b = fig3.add_subplot(gs3[1])
        rsi = self._ec_rsi(closes, 14)
        if rsi is not None and len(rsi) > 0:
            ax3b.plot(x[-len(rsi):], rsi, color="#9C27B0", linewidth=1)
            ax3b.axhline(70, color="#E53935", linestyle="--", linewidth=0.5)
            ax3b.axhline(30, color="#4CAF50", linestyle="--", linewidth=0.5)
            ax3b.fill_between(x[-len(rsi):], 70, 100, alpha=0.1, color="#E53935")
            ax3b.fill_between(x[-len(rsi):], 0, 30, alpha=0.1, color="#4CAF50")
        ax3b.set_title("RSI(14)", fontsize=10)
        ax3b.set_ylim(0, 100)
        ax3b.grid(True, alpha=0.3)

        # 成交量
        ax3c = fig3.add_subplot(gs3[2])
        colors = ["#d32f2f" if closes[i] >= opens[i] else "#388e3c" for i in range(n)]
        ax3c.bar(x, volumes, color=colors, width=0.8)
        ax3c.set_title("成交量", fontsize=10)
        ax3c.grid(True, alpha=0.3)

        fig3.suptitle(f"{sname} 附图指标", fontsize=11)
        fig3.tight_layout()
        FCA(fig3, t3).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._ec_right_nb.add(t3, text="📊 附图指标")

        # ── Tab4: 📐 综合判断 ──
        t4 = tk.Frame(self._ec_right_nb)
        latest_close = closes[-1]
        latest_pct = (closes[-1] - closes[-2]) / closes[-2] * 100 if n > 1 else 0

        # 简单判断
        ma_trend = "多头排列 📈" if (ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]
                                     if len(ma60) > 0 else len(ma20) > 0) else "空头排列 📉" if len(ma20) > 0 else "震荡 ↔"

        rsi_val = rsi[-1] if rsi is not None and len(rsi) > 0 else 50
        rsi_desc = "超买 ⚠️" if rsi_val > 70 else "超卖 💡" if rsi_val < 30 else "中性"

        macd_val = dif[-1] - dea[-1] if len(dif) > 0 else 0
        macd_desc = "金叉 🔔" if dif[-1] > dea[-1] else "死叉 ⚠️"

        info = (
            f"【{sname}】综合判断\n\n"
            f"  💰 现价: {latest_close:.2f}  |  当日涨跌: {latest_pct:+.2f}%\n"
            f"  📈 MA趋势: {ma_trend}\n"
            f"  ⚡ RSI(14): {rsi_val:.1f} — {rsi_desc}\n"
            f"  📊 MACD: {macd_desc} (bar={macd_val:+.4f})\n\n"
            f"  🎯 事件影响: {self._ec_last_event_name if hasattr(self, '_ec_last_event_name') else '财经日历'}\n"
            f"  📌 板块: {self._ec_last_event_sector if hasattr(self, '_ec_last_event_sector') else '-'}\n"
        )
        tk.Label(t4, text=info, font=("TkDefaultFont", 11),
                 justify="left", anchor="nw", padx=20, pady=20,
                 background="#fafafa").pack(fill=tk.BOTH, expand=True)
        self._ec_right_nb.add(t4, text="📐 综合判断")

        self._ec_status.set(f"✅ {sname} K线已加载 ({n}根)")

    # ═══════════════════════════════════════════════════════════════
    # 技术指标辅助 (EMA/RSI — 精简版, 和 tab_stock_detail 解耦)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _ec_ema(data, period):
        """指数移动平均"""
        import numpy as np
        alpha = 2.0 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema

    @staticmethod
    def _ec_rsi(closes, period=14):
        """RSI 指标"""
        import numpy as np
        n = len(closes)
        if n <= period:
            return None
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.convolve(gains, np.ones(period)/period, mode='valid')
        avg_loss = np.convolve(losses, np.ones(period)/period, mode='valid')
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    # ═══════════════════════════════════════════════════════════════
    # 中列双击 → 独立 K 线弹窗
    # ═══════════════════════════════════════════════════════════════

    def _ec_on_mid_double(self, event):
        """中列双击 → 后台拉 K 线 → 独立弹窗"""
        tree = event.widget
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        idx = tree.index(row_id)
        if not hasattr(self, "_ec_mid_data") or idx >= len(self._ec_mid_data):
            return

        s = self._ec_mid_data[idx]
        ts_code = s["ts_code"]
        sname = s["sname"]

        try:
            _base, _suf = ts_code.split(".", 1)
            sina_code = ("sh" if _suf.upper() == "SH" else
                         ("sz" if _suf.upper() == "SZ" else
                          ("bj" if _suf.upper() == "BJ" else ""))) + _base
        except Exception:
            return

        self._ec_status.set(f"⏳ 双击加载 {sname} K线...")

        def _bg():
            try:
                kdata = self._get_daily_kline_data_tushare(sina_code, days=120)
            except Exception as ex:
                self.root.after(0, lambda: self._ec_status.set(
                    f"❌ K线失败: {ex}"))
                return
            if not kdata:
                self.root.after(0, lambda: self._ec_status.set(
                    f"⚠️ {sname} 无K线"))
                return
            self.root.after(0, lambda: self._ec_open_kline_dialog(sina_code, sname))
            self.root.after(0, lambda: self._ec_status.set(
                f"✅ {sname} K线已打开"))

        threading.Thread(target=_bg, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # 刷新 (预留 — 接入实时 API)
    # ═══════════════════════════════════════════════════════════════

    def _ec_refresh_events(self):
        """刷新财经日历 (目前用内置库, 后续可接实时 API)"""
        self._ec_status.set("⏳ 刷新中...")

        def _bg():
            # 尝试 iFinD edb 获取最新宏观指标预告
            try:
                from utils.ifind_client import call as ifind_call
                # 不阻塞, 仅作补充
            except Exception:
                pass
            self.root.after(0, self._ec_refresh_done)

        threading.Thread(target=_bg, daemon=True).start()

    def _ec_refresh_done(self):
        self._ec_events = _build_default_events()
        self._ec_all_events = list(self._ec_events)
        self._ec_fill_left()
        self._ec_status.set(f"✅ 已刷新 {len(self._ec_events)} 个事件")

    # ═══════════════════════════════════════════════════════════════
    # 🔥 完整独立 K 线弹窗 (📈日K / 🌊一目均衡 / 📊附图 / 📐综合)
    # ═══════════════════════════════════════════════════════════════

    def _ec_open_kline_dialog(self, sina_code, sname):
        """中列双击 → 独立 K 线弹窗 (4 tab 完整版本)"""
        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        import numpy as np
        from matplotlib import gridspec as _gs

        dlg = tk.Toplevel(self.root)
        dlg.title(f"📈 {sname} 日K线 + 一目均衡 + 附图指标")
        dlg.geometry("1080x720")
        dlg.transient(self.root)

        nb = ttk.Notebook(dlg)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        tk.Label(nb, text="⏳ 正在拉取 K 线数据...",
                 font=("Menlo", 16), fg="#FFA726").pack(expand=True)
        nb.add(tk.Frame(nb), text="📊 加载中")

        def _bg():
            try: kdf = self._fetch_ichimoku_kline_data(sina_code, period="daily", is_index=False)
            except Exception: kdf = None
            self.root.after(0, lambda: _bg_draw(kdf))

        def _bg_draw(kdf):
            for _t in nb.tabs(): nb.forget(_t)
            if kdf is None or len(kdf) < 30:
                tk.Label(nb, text=f"{sname}\nK线数据不足(<30)",
                         font=("Menlo",14), fg="#E53935").pack(expand=True)
                nb.add(tk.Frame(nb), text="📈 日K线"); return

            opens = kdf["开盘"].astype(float).values if "开盘" in kdf.columns else kdf["open"].astype(float).values
            highs = kdf["最高"].astype(float).values if "最高" in kdf.columns else kdf["high"].astype(float).values
            lows  = kdf["最低"].astype(float).values if "最低" in kdf.columns else kdf["low"].astype(float).values
            closes= kdf["收盘"].astype(float).values if "收盘" in kdf.columns else kdf["close"].astype(float).values
            n = len(closes); x = list(range(n)); up_c, dn_c = "#EF5350", "#66BB6A"
            ma5=np.convolve(closes,np.ones(5)/5,mode='valid'); ma10=np.convolve(closes,np.ones(10)/10,mode='valid')
            ma20=np.convolve(closes,np.ones(20)/20,mode='valid'); ma60=np.convolve(closes,np.ones(60)/60,mode='valid')

            # Tab1: 📈 日K线 + MA
            t1 = tk.Frame(nb); nb.add(t1, text="📈 日K线")
            f1 = Figure(figsize=(11,5), dpi=100); ax1 = f1.add_subplot(111)
            for i in range(n):
                c = up_c if closes[i]>=opens[i] else dn_c
                ax1.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=c, width=0.7)
                ax1.vlines(x[i], lows[i], highs[i], color=c, linewidth=0.5)
            if len(ma5)>=1: ax1.plot(x[4:], ma5, label="MA5", color="#FF9800", linewidth=1.2)
            if len(ma10)>=1: ax1.plot(x[9:], ma10, label="MA10", color="#2196F3", linewidth=1.2)
            if len(ma20)>=1: ax1.plot(x[19:], ma20, label="MA20", color="#9C27B0", linewidth=1.2)
            if len(ma60)>=1: ax1.plot(x[59:], ma60, label="MA60", color="#607D8B", linewidth=1.2)
            ax1.set_title(f"{sname} ({sina_code}) 日K线 {n}根", fontsize=12)
            ax1.legend(fontsize=9, loc="upper left"); ax1.grid(True, alpha=0.3)
            f1.tight_layout(); FigureCanvasTkAgg(f1, t1).get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Tab2: 🌊 一目均衡
            t2 = tk.Frame(nb); nb.add(t2, text="🌊 一目均衡")
            try:
                ich = self._calc_ichimoku(highs, lows, closes)
                f2 = Figure(figsize=(11,5), dpi=100); ax2 = f2.add_subplot(111)
                for i in range(n):
                    c = up_c if closes[i]>=opens[i] else dn_c
                    ax2.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=c, width=0.7)
                    ax2.vlines(x[i], lows[i], highs[i], color=c, linewidth=0.5)
                ext_x = list(range(n + 26))
                ax2.plot(ext_x[:len(ich["tenkan"])], ich["tenkan"], color="#FF9800", linewidth=1.2, label="转换线")
                ax2.plot(ext_x[:len(ich["kijun"])], ich["kijun"], color="#2196F3", linewidth=1.2, label="基准线")
                ax2.plot(ext_x[:len(ich["senkou_a"])], ich["senkou_a"], color="#9C27B0", linewidth=1.2, label="先行带A")
                ax2.plot(ext_x[:len(ich["senkou_b"])], ich["senkou_b"], color="#607D8B", linewidth=1.2, label="先行带B")
                ax2.fill_between(ext_x[:len(ich["senkou_a"])], ich["senkou_a"], ich["senkou_b"],
                                 where=np.array(ich["senkou_a"])>=np.array(ich["senkou_b"]), alpha=0.15, color="#9C27B0")
                ax2.fill_between(ext_x[:len(ich["senkou_a"])], ich["senkou_a"], ich["senkou_b"],
                                 where=np.array(ich["senkou_a"])<np.array(ich["senkou_b"]), alpha=0.15, color="#607D8B")
                ax2.plot(ext_x[:len(ich["chikou"])], ich["chikou"], color="#4CAF50", linewidth=1.2, label="迟行带")
                ax2.set_title(f"{sname} 一目均衡图", fontsize=12)
                ax2.legend(fontsize=9, loc="upper left"); ax2.grid(True, alpha=0.3)
                f2.tight_layout(); FigureCanvasTkAgg(f2, t2).get_tk_widget().pack(fill=tk.BOTH, expand=True)
            except Exception as ex:
                tk.Label(t2, text=f"一目均衡计算失败: {ex}", fg="#E53935").pack(pady=20)

            # Tab3: 📊 附图指标 (MACD + RSI + KDJ)
            t3 = tk.Frame(nb); nb.add(t3, text="📊 附图指标")
            f3 = Figure(figsize=(11,7), dpi=100); gs3 = _gs.GridSpec(4,1,height_ratios=[3,1,1,1], hspace=0.35)
            ax3 = f3.add_subplot(gs3[0]); ax_macd = f3.add_subplot(gs3[1])
            ax_rsi = f3.add_subplot(gs3[2]); ax_kdj = f3.add_subplot(gs3[3])
            for i in range(n):
                c = up_c if closes[i]>=opens[i] else dn_c
                ax3.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=c, width=0.7)
                ax3.vlines(x[i], lows[i], highs[i], color=c, linewidth=0.5)
            ax3.plot(x[4:], ma5, label="MA5", color="#FF9800", linewidth=0.9)
            ax3.plot(x[19:], ma20, label="MA20", color="#9C27B0", linewidth=0.9)
            ax3.set_title(f"{sname} K线 + MACD + RSI + KDJ", fontsize=11); ax3.legend(fontsize=8); ax3.grid(True, alpha=0.3)
            # MACD
            ema12=np.zeros(n); ema26=np.zeros(n); ema12[0]=closes[0]; ema26[0]=closes[0]
            for i in range(1,n): ema12[i]=ema12[i-1]*11/13+closes[i]*2/13; ema26[i]=ema26[i-1]*25/27+closes[i]*2/27
            dif=ema12-ema26; dea=np.zeros(n); dea[0]=dif[0]
            for i in range(1,n): dea[i]=dea[i-1]*8/10+dif[i]*2/10
            macd=(dif-dea)*2; macd_colors=[up_c if v>=0 else dn_c for v in macd]
            ax_macd.bar(x, macd, color=macd_colors, width=0.7); ax_macd.plot(x, dif, color="#FF9800", linewidth=0.8, label="DIF")
            ax_macd.plot(x, dea, color="#2196F3", linewidth=0.8, label="DEA"); ax_macd.legend(fontsize=7); ax_macd.grid(True, alpha=0.3)
            # RSI(14)
            rsi=np.zeros(n); rsi[0]=50
            for i in range(1,n):
                if i<14: avg_up=np.mean([max(closes[j]-closes[j-1],0) for j in range(1,i+1)]); avg_dn=np.mean([max(closes[j-1]-closes[j],0) for j in range(1,i+1)])
                else: avg_up=np.mean([max(closes[j]-closes[j-1],0) for j in range(i-13,i+1)]); avg_dn=np.mean([max(closes[j-1]-closes[j],0) for j in range(i-13,i+1)])
                rs=avg_up/avg_dn if avg_dn>0 else 100; rsi[i]=100-100/(1+rs)
            ax_rsi.plot(x, rsi, color="#9C27B0", linewidth=0.8); ax_rsi.axhline(70, color="#E53935", linestyle="--", linewidth=0.7)
            ax_rsi.axhline(30, color="#4CAF50", linestyle="--", linewidth=0.7); ax_rsi.set_ylim(0,100); ax_rsi.grid(True, alpha=0.3)
            # KDJ(9,3,3)
            kdj_k=np.zeros(n); kdj_d=np.zeros(n); kdj_j=np.zeros(n); kdj_k[0]=50; kdj_d[0]=50
            for i in range(1,n):
                ll=max(0,i-9); low9=np.min(lows[ll:i+1]); high9=np.max(highs[ll:i+1])
                rsv=(closes[i]-low9)/(high9-low9)*100 if high9>low9 else 50
                kdj_k[i]=kdj_k[i-1]*2/3+rsv*1/3; kdj_d[i]=kdj_d[i-1]*2/3+kdj_k[i]*1/3; kdj_j[i]=3*kdj_k[i]-2*kdj_d[i]
            ax_kdj.plot(x, kdj_k, color="#FF9800", linewidth=0.8, label="K"); ax_kdj.plot(x, kdj_d, color="#2196F3", linewidth=0.8, label="D")
            ax_kdj.plot(x, kdj_j, color="#E53935", linewidth=0.8, label="J"); ax_kdj.axhline(80, color="#E53935", linestyle="--", linewidth=0.7)
            ax_kdj.axhline(20, color="#4CAF50", linestyle="--", linewidth=0.7); ax_kdj.grid(True, alpha=0.3)
            f3.tight_layout(); FigureCanvasTkAgg(f3, t3).get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Tab4: 📐 综合判断
            t4 = tk.Frame(nb); nb.add(t4, text="📐 综合判断")
            last_price = closes[-1]; last_ma20 = ma20[-1] if len(ma20)>0 else 0
            last_ma60 = ma60[-1] if len(ma60)>0 else 0
            ma_align = "多头排列 📈" if ma5[-1]>ma20[-1]>ma60 else ("空头排列 📉" if ma5[-1]<ma20[-1]<ma60 else "震荡整理 ⚖️")
            ma_pos = "站上" if last_price>last_ma20 else "跌破" if last_price<last_ma20 else "贴近"
            rsi_status = "超买 ⚠️" if rsi[-1]>70 else "超卖 💎" if rsi[-1]<30 else "中性"
            kdj_status = "金叉 🟢" if kdj_j[-1]>kdj_k[-1] and kdj_k[-1]>kdj_d[-1] else "死叉 🔴" if kdj_j[-1]<kdj_k[-1] and kdj_k[-1]<kdj_d[-1] else "中性"
            macd_status = "多头强势 📈" if macd[-1]>0 and dif[-1]>dea[-1] else "空头强势 📉" if macd[-1]<0 and dif[-1]<dea[-1] else "转折中 🔄"
            try:
                tenkan_now = ich["tenkan"][-1]; kijun_now = ich["kijun"][-1]
                cloud_a = ich["senkou_a"][-1]; cloud_b = ich["senkou_b"][-1]
                ich_status = "强势 🟢" if last_price>cloud_a and cloud_a>cloud_b else "弱势 🔴" if last_price<cloud_b and cloud_a<cloud_b else "震荡 ⚪"
                tk_align = "金叉 🟡" if tenkan_now>kijun_now else "死叉 🔵"
            except: ich_status="—"; tk_align="—"
            bull_points, bear_points = [], []
            if ma_pos == "站上": bull_points.append(f"📈 股价站上MA20")
            if ma_align.startswith("多头"): bull_points.append("✨ MA5/MA20/MA60 多头排列")
            if rsi_status != "超买": bull_points.append(f"💪 RSI={rsi[-1]:.0f} 利于上行")
            if macd_status.startswith("多头"): bull_points.append("🚀 MACD 多头金叉")
            if ich_status == "强势": bull_points.append("☁️ 一目均衡 强势区")
            if ma_pos == "跌破": bear_points.append(f"📉 股价跌破MA20")
            if ma_align.startswith("空头"): bear_points.append("⚠️ MA5/MA20/MA60 空头排列")
            if rsi_status == "超买": bear_points.append(f"🚨 RSI超买警惕")
            if macd_status.startswith("空头"): bear_points.append("🛑 MACD 空头死叉")
            if ich_status == "弱势": bear_points.append("⛈️ 一目均衡 弱势区")
            result_text = f"""╔══════════════════════════════════════╗
║  📐 {sname} 技术面综合判断
╚══════════════════════════════════════╝

  💹 最新价: {last_price:.2f}  |  MA5: {ma5[-1]:.2f}  |  MA20: {last_ma20:.2f}  |  MA60: {last_ma60:.2f}
  📊 MA 排列: {ma_align}  |  位置: {ma_pos} MA20

  🔥 MACD: {macd_status}  (DIF={dif[-1]:.3f}, DEA={dea[-1]:.3f})
  💪 RSI(14): {rsi_status}  (RSI={rsi[-1]:.1f})
  📍 KDJ: {kdj_status}  (K={kdj_k[-1]:.1f}, D={kdj_d[-1]:.1f}, J={kdj_j[-1]:.1f})
  ☁️ 一目均衡: {ich_status}  |  TK={tk_align}

  🟢 看多信号 ({len(bull_points)}):
{chr(10).join(f'    • {p}' for p in bull_points) if bull_points else '    (无)'}

  🔴 看空信号 ({len(bear_points)}):
{chr(10).join(f'    • {p}' for p in bear_points) if bear_points else '    (无)'}

  🎯 综合评分: {max(0,min(100,50 + len(bull_points)*10 - len(bear_points)*10))}/100
  ⚠️ 以上仅为技术面量化分析, 不构成投资建议
"""
            txt = tk.Text(t4, wrap=tk.WORD, font=("Menlo", 11), bg="#FAFAFA", borderwidth=0, padx=10, pady=10)
            txt.pack(fill=tk.BOTH, expand=True); txt.insert("1.0", result_text); txt.configure(state=tk.DISABLED)

        threading.Thread(target=_bg, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # 右列: 信息 + 新闻 + 财经日历影响分析
    # ═══════════════════════════════════════════════════════════════

    def _ec_build_right_info_panel(self, sina_code, sname, ev_name=""):
        """右列: 股票基本信息 + 新闻资讯 + 财经日历影响分析"""
        import sqlite3 as _sql3
        for _t in self._ec_right_nb.tabs(): self._ec_right_nb.forget(_t)

        # ── Tab1: 📋 股票信息快览 ──
        t1 = tk.Frame(self._ec_right_nb); self._ec_right_nb.add(t1, text="📋 股票信息")
        ttk.Label(t1, text=f"📊 {sname} ({sina_code})", font=("", 14, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        info_f = tk.Frame(t1); info_f.pack(fill=tk.X, padx=10, pady=5)
        info_data = [("代码", sina_code), ("名称", sname),
                     ("所属板块", self._ec_get_sector_for_stock(sina_code)),
                     ("关联事件", ev_name or "—")]
        for i, (k, v) in enumerate(info_data):
            tk.Label(info_f, text=f"{k}:", font=("", 10, "bold"), fg="#555").grid(row=i, column=0, sticky="w", padx=5, pady=2)
            tk.Label(info_f, text=str(v), font=("", 10), fg="#222").grid(row=i, column=1, sticky="w", padx=5, pady=2)
        links_f = tk.LabelFrame(t1, text="🔗 快速链接 (点击打开)", font=("", 10, "bold"))
        links_f.pack(fill=tk.X, padx=10, pady=10)
        _suffix = sina_code[-6:]; _prefix = sina_code[:2]
        _links = [
            ("📈 同花顺行情", f"https://stockpage.10jqka.com.cn/{_suffix}/"),
            ("📊 东方财富", f"https://quote.eastmoney.com/{sina_code}.html"),
            ("📰 新浪财经", f"https://finance.sina.com.cn/realstock/{_prefix}/n{_suffix}.shtml"),
            ("📯 淘股吧搜索", f"https://www.tgb.cn/search?keyword={_suffix}"),
        ]
        for label, url in _links:
            tk.Button(links_f, text=label, fg="#1565C0", cursor="hand2",
                      font=("", 10, "underline"), relief=tk.FLAT,
                      command=lambda u=url: _wb_ec.open(u)).pack(anchor="w", padx=10, pady=2)

        # ── Tab2: 📰 新闻资讯 ──
        t2 = tk.Frame(self._ec_right_nb); self._ec_right_nb.add(t2, text="📰 新闻资讯")
        news_tb = ttk.Notebook(t2); news_tb.pack(fill=tk.BOTH, expand=True)
        n1 = tk.Frame(news_tb); news_tb.add(n1, text="📯 淘股吧热文")
        n2 = tk.Frame(news_tb); news_tb.add(n2, text="🧭 韭研公社")
        n3 = tk.Frame(news_tb); news_tb.add(n3, text="📚 本地文章库")
        self._ec_fill_news_listbox(n1, sina_code, "taoguba")
        self._ec_fill_news_listbox(n2, sina_code, "jiuyan")
        self._ec_fill_news_listbox(n3, sina_code, "db")

        # ── Tab3: 📋 财经日历影响分析 ──
        t3 = tk.Frame(self._ec_right_nb); self._ec_right_nb.add(t3, text="📋 事件影响")
        analysis_text = self._ec_build_impact_analysis(sina_code, sname, ev_name)
        txt = tk.Text(t3, wrap=tk.WORD, font=("Menlo", 11), bg="#FFF8E1", borderwidth=0, padx=12, pady=12)
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        txt.insert("1.0", analysis_text); txt.configure(state=tk.DISABLED)

        # ── Tab4: 📊 技术面快览 ──
        t4 = tk.Frame(self._ec_right_nb); self._ec_right_nb.add(t4, text="📊 技术面快览")
        self._ec_show_tech_quick(sina_code, sname, t4)

    def _ec_get_sector_for_stock(self, sina_code):
        _SECTOR_MAP = {
            "sh600": "沪市主板", "sh601": "沪市主板", "sh603": "沪市主板",
            "sh688": "科创板", "sz000": "深市主板", "sz001": "深市主板",
            "sz002": "中小板", "sz003": "深市主板",
            "sz300": "创业板", "sz301": "创业板",
        }
        for prefix, sec in _SECTOR_MAP.items():
            if sina_code.startswith(prefix): return sec
        return "A股"

    def _ec_fill_news_listbox(self, parent, sina_code, source):
        """填充新闻列表"""
        import sqlite3 as _sql3
        items = []
        if source in ["taoguba", "jiuyan"]:
            _attr = f"_{source}_stamp_data"
            for r in (getattr(self, _attr, None) or []):
                if r.get("code") != sina_code: continue
                freq = r.get("freq", 1); pct = r.get("pct", 0)
                items.append(({"title": f"🔥 {r.get('origin', source)}  提及{freq}次  涨跌{pct:+.2f}%"}, "header"))
                for _art in r.get("articles", [])[:5]:
                    if isinstance(_art, dict): items.append((_art, "art"))
                    elif isinstance(_art, str): items.append(({"title": _art}, "art"))
        elif source == "db":
            for _dp in ["stock_analysis.db",
                        f"{_os_ec.path.dirname(_os_ec.path.abspath(__file__))}/../../data/stock_analysis.db",
                        "/Users/faronpan/Agent/stockyidong_project/data/stock_analysis.db"]:
                if not _os_ec.path.exists(_dp): continue
                try:
                    conn = _sql3.connect(_dp); cur = conn.cursor()
                    _code6 = sina_code[-6:]
                    for cand in [_code6, sina_code]:
                        cur.execute("SELECT title, source, substr(content,1,120), url, created_at FROM articles WHERE stock_code LIKE ? ORDER BY created_at DESC LIMIT 8", (f"%{cand}%",))
                        for row in cur.fetchall():
                            items.append(({"title": f"📚{row[1] or ''}  🕐{(row[4] or '')[:10]}  {row[0] or ''}",
                                           "summary": row[2] or "", "url": row[3] or ""}, "art"))
                    conn.close(); break
                except: pass

        if not items:
            tk.Label(parent, text="  (暂无匹配文章)", fg="#999", font=("", 10)).pack(pady=20); return

        canvas = tk.Canvas(parent, highlightthickness=0, bg="#FAFAFA")
        sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg="#FAFAFA")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for it, tp in items:
            title = it.get("title", "") if isinstance(it, dict) else str(it)
            if tp == "header":
                tk.Label(inner, text=title, bg="#FFF3E0", fg="#E65100",
                         font=("", 10, "bold"), anchor="w").pack(fill=tk.X, pady=(4, 0), padx=4)
            else:
                row_f = tk.Frame(inner, bg="#FAFAFA"); row_f.pack(fill=tk.X, pady=2, padx=4)
                _fg = "#1565C0" if source in ["taoguba", "db"] else "#2E7D32"
                url = it.get("url", "") if isinstance(it, dict) else ""
                lbl = tk.Label(row_f, text=f"📰 {title[:70]}", bg="#FAFAFA", fg=_fg,
                               font=("", 10), cursor="hand2" if url else "")
                lbl.pack(anchor="w")
                if url:
                    lbl.bind("<Button-1>", lambda e, u=url: _wb_ec.open(u))
                    lbl.configure(font=("", 10, "underline"))
                if isinstance(it, dict) and it.get("summary"):
                    tk.Label(row_f, text=f"    💡 {it['summary'][:80]}", bg="#FAFAFA", fg="#666", font=("", 9)).pack(anchor="w")

    def _ec_build_impact_analysis(self, sina_code, sname, ev_name):
        lines = ["╔══════════════════════════════════════╗",
                 f"║  📋 财经事件对 {sname} 的影响分析",
                 "╚══════════════════════════════════════╝", "",
                 f"  💹 归属市场: {self._ec_get_sector_for_stock(sina_code)}  |  代码: {sina_code}", ""]
        if hasattr(self, "_ec_current_event") and self._ec_current_event:
            ev = self._ec_current_event
            lines.append(f"  📅 当前事件: {ev.get('name', ev_name or '—')}")
            lines.append(f"  🌏 发生地: {ev.get('country', '—')}  |  重要度: {ev.get('importance', '⭐')}")
            lines.append(f"  📌 影响板块: {ev.get('sector', '—')}")
            lines.append(f"  📝 事件描述: {ev.get('desc', '—')}")
            lines.append("")
            ev_sector = ev.get("sector", "")
            impact_map = {
                "LPR/利率": ("🟢 利率下行→利好地产融资成本/保险", "🔴 利率上行→利空地产/成长估值"),
                "CPI/通胀": ("🟢 温和通胀→利好消费升级/白酒", "🔴 高通胀→央行可能收紧"),
                "FOMC/议息": ("🟢 降息预期→利好黄金/新兴市场", "🔴 加息→利空黄金/出口竞争力"),
                "OPEC/原油": ("🟢 减产→利好石油公司利润", "🔴 增产→利空能源股/利好化工成本"),
                "PMI/制造": ("🟢 PMI↑→利好周期/基建", "🔴 PMI↓→利空制造业链条"),
            }
            for _k, (pos, neg) in impact_map.items():
                if _k in ev_sector:
                    lines.append(f"  🎯 影响方向:")
                    lines.append(f"    {pos}"); lines.append(f"    {neg}"); break
            else:
                lines.append(f"  🎯 影响方向: {ev_sector} 板块通常受此事件直接影响")
        else:
            lines.append("  💡 提示: 请先在左列点击财经事件")
        lines.extend(["", "  📌 操作提示:",
                      "    • 重要事件前 1-2 个交易日常有异动",
                      "    • 事件确认后, 利好兑现是卖点",
                      "    • 双击中列股票→完整 K 线 + 技术面",
                      "    • ⚠️ 以上仅为逻辑推演, 不构成投资建议"])
        return "\n".join(lines)

    def _ec_show_tech_quick(self, sina_code, sname, parent):
        ttk.Label(parent, text=f"⏳ 正在计算 {sname} 技术指标...", font=("", 11)).pack(pady=20)
        def _bg():
            try: kdf = self._fetch_ichimoku_kline_data(sina_code, period="daily", is_index=False)
            except Exception: kdf = None
            self.root.after(0, lambda: _bg_draw(kdf))
        def _bg_draw(kdf):
            for w in parent.winfo_children(): w.destroy()
            if kdf is None or len(kdf) < 30:
                tk.Label(parent, text=f"❌ K线数据不足", fg="#E53935", font=("", 12)).pack(pady=20); return
            closes = kdf["收盘"].astype(float).values if "收盘" in kdf.columns else kdf["close"].astype(float).values
            n = len(closes); last = closes[-1]
            ma5=sum(closes[-5:])/min(5,n); ma20=sum(closes[-20:])/min(20,n); ma60=sum(closes[-60:])/min(60,n)
            chg = (last - closes[-2])/closes[-2]*100 if n>1 else 0
            h20=max(closes[-20:]) if n>=20 else max(closes); l20=min(closes[-20:]) if n>=20 else min(closes)
            panel = tk.LabelFrame(parent, text="📊 技术面快览", font=("", 11, "bold"))
            panel.pack(fill=tk.X, padx=10, pady=10)
            rows = [
                ("最新价", f"{last:.2f} ({chg:+.2f}%)", "#d32f2f" if chg>=0 else "#388e3c"),
                ("MA5 / MA20 / MA60", f"{ma5:.2f} / {ma20:.2f} / {ma60:.2f}", "#333"),
                ("MA 位置", "✅ 站上MA20" if last>ma20 else "❌ 跌破MA20", "#2E7D32" if last>ma20 else "#E53935"),
                ("距 20 日高点", f"{(last-h20)/h20*100:+.1f}%", "#d32f2f"),
                ("距 20 日低点", f"{(last-l20)/l20*100:+.1f}%", "#388e3c"),
            ]
            for i, (k, v, c) in enumerate(rows):
                tk.Label(panel, text=k, font=("", 10, "bold"), fg="#555").grid(row=i, column=0, sticky="w", padx=10, pady=4)
                tk.Label(panel, text=v, font=("", 10), fg=c).grid(row=i, column=1, sticky="w", padx=10, pady=4)
        threading.Thread(target=_bg, daemon=True).start()
