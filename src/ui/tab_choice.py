"""东方财富 Choice 金融数据弹窗 Mixin

核心功能:
  - 🏒 涨停/跌停/连板股池 (东方财富源)
  - 🐉 龙虎榜每日明细
  - 📊 宏观数据 (GDP/CPI/PMI)
  - 💰 国债收益率曲线
  - 📈 财务摘要 (同花顺源)
  - 🎯 妙想 MCP 一键查询 (需 API key)

数据源优先级:
  1. 妙想 MCP (mxapi.eastmoney.com) — 用户填 EASTMONEY_APIKEY
  2. 妙想 Skills (mkapi2.dfcfs.com) — 用户填 apikey
  3. akshare 公开数据源 (无需 key)
"""
from __future__ import annotations

import json
import os
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

import requests

try:
    import akshare as ak
except ImportError:
    ak = None


# ── 妙想 MCP endpoint ──
MIAOXIANG_MCP_URL = "https://mxapi.eastmoney.com/mxds/mcp"
MIAOXIANG_SKILLS_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"

# ── 妙想 MCP 11 个工具 ──
MCP_TOOLS = {
    "mx_ashare_finance_data":       ("🏒", "A股数据",   "股票行情/财务/估值/股东/事件"),
    "mx_fund_finance_data":         ("💰", "基金数据",   "基金净值/业绩/持仓/分红/公司"),
    "mx_bond_finance_data":         ("📜", "债券数据",   "债券基本/行情/估值/信用评级"),
    "mx_index_block_finance_data":  ("📊", "指数板块",   "指数/行业/概念/板块行情指标"),
    "mx_us_finance_data":           ("🇺🇸", "美股数据",   "美股行情/财务/IPO/回购/分红"),
    "mx_hk_finance_data":           ("🇭🇰", "港股数据",   "港股行情/财务/估值/IPO/分红"),
    "mx_comprehensive_finance_data":("🏢", "综合企业",   "跨市场/非上市公司/企业发行人"),
    "mx_macro_data":                ("🌍", "宏观经济",   "GDP/CPI/PMI/利率/大宗商品"),
    "mx_stocks_screener":           ("🎯", "多维选股",   "按条件筛选股票/基金/债券"),
    "mx_finance_search_news":       ("📰", "资讯新闻",   "研报/评级/目标价/行业新闻"),
    "mx_finance_search_notice":     ("📋", "公告披露",   "上市公司公告/定期报告/重大事项"),
}

# ── MCP 分类模板 ──
MCP_TEMPLATES = {
    "🏒 A股": [
        ("mx_ashare_finance_data", "贵州茅台最新市值、PE(TTM)、股价"),
        ("mx_ashare_finance_data", "宁德时代近10日涨跌幅和换手率"),
        ("mx_ashare_finance_data", "比亚迪2025三季报营收和净利润"),
        ("mx_ashare_finance_data", "格力电器上市时间和最近分红"),
    ],
    "🌍 宏观": [
        ("mx_macro_data", "中国2026年三季度GDP同比增速"),
        ("mx_macro_data", "最新CPI和PPI数据"),
        ("mx_macro_data", "美联储联邦基金利率历史走势"),
        ("mx_macro_data", "原油价格近6个月走势"),
    ],
    "🎯 选股": [
        ("mx_stocks_screener", "市盈率低于20倍的医药股"),
        ("mx_stocks_screener", "股价创新高的新能源股票"),
        ("mx_stocks_screener", "创业板市值前10的股票"),
        ("mx_stocks_screener", "北向资金连续5日净买入的股票"),
    ],
    "💰 基金": [
        ("mx_fund_finance_data", "工银双盈债券A(010068)最新净值"),
        ("mx_fund_finance_data", "易方达蓝筹精选前十大重仓股"),
        ("mx_fund_finance_data", "近一年收益率最高的公募基金TOP10"),
    ],
    "📰 资讯": [
        ("mx_finance_search_news", "中信证券最新研报观点"),
        ("mx_finance_search_news", "半导体板块近期利好消息"),
        ("mx_finance_search_notice", "格力电器最新分红公告"),
        ("mx_finance_search_notice", "比亚迪最新增发公告"),
    ],
    "🚀 机构增持": [
        ("mx_stocks_screener", "2026中报机构数量较2025年报增长超过50%的股票，按机构增长率排序，显示机构持股家数环比增长率、上期机构家数、本期机构家数、净利润增长率、总市值"),
        ("mx_stocks_screener", "北向资金+机构持仓同时大幅增加的股票TOP30，显示沪深股通净买入额、机构持股较上期变化、涨跌幅、市盈率、总市值"),
        ("mx_stocks_screener", "机构持仓占总股本比例上升最快的A股TOP30，显示机构持股占比变化、机构数量变化、累计持股变化、净利润增长率"),
    ],
}

# API key 存储 (用户填了就持久化)
_CHOICE_KEY_PATH = os.path.expanduser("~/.choice_apikey.json")

import re


def _clean_choice_key(raw: str) -> str:
    """从用户粘贴的任意文本中提取真正的 API Key
    
    用户常把整行 'API Key 查看\n您的专属 API Key\nem_xxx' 复制进来,
    这里用正则精确提取常见格式的 token:
      - em_xxx   (妙想 Skills API)
      - mkt_xxx  (妙想 MCP)  
      - 纯 hex 40+ 位 token
    """
    if not raw:
        return ""
    raw = raw.strip()
    # 1. em_ / mkt_ 开头
    for prefix in ("em_", "mkt_"):
        m = re.search(rf'({prefix}[a-zA-Z0-9_\-]+)', raw)
        if m:
            return m.group(1)
    # 2. 纯 hex 32+ 位
    m = re.search(r'([a-f0-9]{32,})', raw)
    if m:
        return m.group(1)
    # 3. 兜底: 取最后一个单词 (用户直接粘贴 key 时)
    tokens = re.findall(r'[a-zA-Z0-9_\-]{16,}', raw)
    if tokens:
        return tokens[-1]
    return re.sub(r'[^a-zA-Z0-9_\-]', '', raw)


def _load_apikey() -> dict:
    try:
        data = json.loads(open(_CHOICE_KEY_PATH).read())
        # 自动清理已存的旧 key (兼容之前带垃圾的)
        if data.get("skills_apikey"):
            data["skills_apikey"] = _clean_choice_key(data["skills_apikey"])
        if data.get("mx_apikey"):
            data["mx_apikey"] = _clean_choice_key(data["mx_apikey"])
        return data
    except Exception:
        return {}


def _save_apikey(data: dict):
    try:
        cleaned = {k: _clean_choice_key(v) for k, v in data.items() if v}
        open(_CHOICE_KEY_PATH, "w").write(json.dumps(cleaned))
    except Exception:
        pass


def _mask_key(k: str) -> str:
    """只显示前 10 位 + ***"""
    if not k:
        return ""
    return k[:10] + "***" if len(k) > 10 else k + "***"


class ChoiceMixin:
    """东方财富 Choice / 妙想 数据弹窗"""

    # 📋 功能清单
    _CHOICE_FEATURES = [
        ("🏒 涨停股池", "zt_pool"),
        ("🐉 龙虎榜明细", "lhb"),
        ("📊 宏观·GDP", "gdp"),
        ("📊 宏观·CPI", "cpi"),
        ("📊 宏观·PMI", "pmi"),
        ("💰 国债收益率", "bond_yield"),
        ("📈 个股财务摘要", "financial"),
        ("🧠 妙想 AI 查询", "miaoxiang"),
    ]

    # 📋 快捷模板 (妙想 AI 用)
    _CHOICE_TEMPLATES = [
        "宁德时代最新价和市值",
        "贵州茅台 2025 年三季报净利润",
        "今日涨停股票列表",
        "比亚迪和特斯拉 PE 对比",
        "半导体板块今日资金流向",
        "2026 年三季度 GDP 同比增速",
        "新能源汽车行业龙头排名",
        "北向资金今日净买入 TOP10",
    ]

    # ═══════════════════════════════════════════════════════════
    # 🎯 主入口
    # ═══════════════════════════════════════════════════════════

    def _show_choice_dialog(self):
        """🎯 东方财富 Choice / 妙想 弹窗"""
        dlg = tk.Toplevel(self.root)
        dlg.title("🎯 Choice · 东方财富 / 妙想 金融数据")
        dlg.geometry("1420x840")
        dlg.transient(self.root)

        # ── 顶栏 ──
        topbar = ttk.Frame(dlg)
        topbar.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(topbar, text="🎯 Choice · 东方财富 / 妙想",
                 font=("", 13, "bold")).pack(side=tk.LEFT)
        self._choice_status = tk.StringVar(value="就绪")
        ttk.Label(topbar, textvariable=self._choice_status,
                  foreground="gray").pack(side=tk.LEFT, padx=12)

        # API Key 提示
        keys = _load_apikey()  # 自动清理旧 key
        has_key = bool(keys.get("mx_apikey") or keys.get("skills_apikey"))
        real_key = keys.get("skills_apikey") or ""
        if has_key and real_key:
            key_hint = f"妙想 API Key: ✅ {_mask_key(real_key)}"
        elif has_key:
            key_hint = "妙想 API Key: ✅ 已配置"
        else:
            key_hint = "妙想 API Key: ⚠️ 未配置 (可用公开 akshare)"
        ttk.Label(topbar, text=key_hint,
                  foreground="#FF6600").pack(side=tk.RIGHT, padx=12)
        ttk.Button(topbar, text="🔑 配置 API Key",
                   command=lambda: self._choice_config_apikey(dlg)).pack(side=tk.RIGHT)

        # ── 三列 PanedWindow ──
        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ═══ 左列: 功能入口 + 模板 ═══
        left_frame = ttk.Frame(pw, width=230)
        pw.add(left_frame, weight=0)

        tk.Label(left_frame, text="🔍 功能",
                 font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(4, 4))

        self._choice_feat_lb = tk.Listbox(left_frame, selectmode=tk.SINGLE,
                                           font=("", 11), activestyle="dotbox",
                                           height=10)
        for label, _ in self._CHOICE_FEATURES:
            self._choice_feat_lb.insert(tk.END, label)
        self._choice_feat_lb.pack(fill=tk.X, padx=4)
        self._choice_feat_lb.bind("<<ListboxSelect>>",
                                   lambda e: self._choice_on_feat_select())

        # 日期选择
        tk.Label(left_frame, text="📅 日期",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(8, 2))
        today = time.strftime("%Y%m%d")
        self._choice_date_var = tk.StringVar(value=today)
        date_frame = ttk.Frame(left_frame)
        date_frame.pack(fill=tk.X, padx=4)
        ttk.Entry(date_frame, textvariable=self._choice_date_var,
                   font=("", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(date_frame, text="今日", width=4,
                    command=lambda: self._choice_date_var.set(today)).pack(side=tk.LEFT, padx=2)

        # 代码输入 (个股查询用)
        tk.Label(left_frame, text="🏷️ 股票代码",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(8, 2))
        self._choice_code_var = tk.StringVar(value="600519")
        ttk.Entry(left_frame, textvariable=self._choice_code_var,
                  font=("", 10)).pack(fill=tk.X, padx=4)

        # MCP 快捷按钮 (常用工具)
        tk.Label(left_frame, text="⚡ MCP 快捷",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(10, 2))
        mcp_quick_frame = ttk.Frame(left_frame)
        mcp_quick_frame.pack(fill=tk.X, padx=4)
        # 2 列常用按钮
        quick_tools = [
            ("mx_ashare_finance_data", "🏒 A股"),
            ("mx_macro_data", "🌍 宏观"),
            ("mx_stocks_screener", "🎯 选股"),
            ("mx_finance_search_news", "📰 资讯"),
            ("mx_fund_finance_data", "💰 基金"),
            ("mx_index_block_finance_data", "📊 指数"),
        ]
        for i, (tool, label) in enumerate(quick_tools):
            btn = ttk.Button(mcp_quick_frame, text=label, width=6,
                             command=lambda t=tool: self._choice_do_mcp(t))
            btn.grid(row=i // 2, column=i % 2, padx=2, pady=1, sticky="ew")
        mcp_quick_frame.columnconfigure(0, weight=1)
        mcp_quick_frame.columnconfigure(1, weight=1)

        # MCP 分类模板 (可展开)
        self._choice_mcp_tpl_frame = ttk.Frame(left_frame)
        self._choice_mcp_tpl_visible = tk.BooleanVar(value=False)

        def _toggle_mcp_tpl():
            if self._choice_mcp_tpl_visible.get():
                self._choice_mcp_tpl_frame.pack_forget()
                self._choice_mcp_tpl_visible.set(False)
            else:
                self._choice_mcp_tpl_frame.pack(fill=tk.X, padx=4, pady=2)
                self._choice_mcp_tpl_visible.set(True)

        ttk.Button(left_frame, text="📋 MCP 模板 ▼", width=14,
                   command=_toggle_mcp_tpl).pack(anchor="w", padx=6, pady=(6, 2))
        # 先隐藏, 点按钮再展开
        # 填充模板内容
        for cat, tpls in MCP_TEMPLATES.items():
            cat_frame = ttk.LabelFrame(self._choice_mcp_tpl_frame, text=cat, padding=2)
            cat_frame.pack(fill=tk.X, padx=2, pady=2)
            for tool, q in tpls[:3]:  # 每类最多 3 个
                btn = tk.Button(cat_frame, text=q, cursor="hand2", relief=tk.FLAT,
                                fg="#FF6600", font=("", 8), anchor="w", pady=0,
                                wraplength=200, justify="left",
                                command=lambda t=tool, qq=q: (
                                    self._choice_query_ent.delete(0, tk.END),
                                    self._choice_query_ent.insert(0, qq),
                                    self._choice_do_mcp(t)))
                btn.pack(anchor="w", padx=2, fill=tk.X)

        # 妙想 AI 模板 (原有的 + 新增)
        tk.Label(left_frame, text="🤖 AI 自由问答",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(10, 2))
        for tpl in self._CHOICE_TEMPLATES[:4]:
            btn = tk.Button(left_frame, text=tpl, cursor="hand2", relief=tk.FLAT,
                            fg="#666", font=("", 9), anchor="w", pady=1,
                            command=lambda tt=tpl: self._choice_preset(tt))
            btn.pack(anchor="w", padx=6)

        # 妙想 Web 入口
        sep = ttk.Separator(left_frame, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, padx=6, pady=(10, 4))
        tk.Label(left_frame, text="🔗 妙想 Web",
                 font=("", 10, "bold")).pack(anchor="w", padx=6)
        for label, url in [
            ("💎 Choice 终端", "https://choice.eastmoney.com/"),
            ("🧠 妙想 MCP", "https://choice.eastmoney.com/mcp/"),
            ("📊 妙想 Skills", "https://ai.eastmoney.com/miaoxiang/"),
        ]:
            tk.Button(left_frame, text=label, cursor="hand2", relief=tk.FLAT,
                       fg="#FF6600", font=("", 9), anchor="w",
                       command=lambda u=url: webbrowser.open_new_tab(u))\
                .pack(anchor="w", padx=6)

        # ═══ 中列: 搜索框 + Notebook + Treeview ═══
        mid_frame = ttk.Frame(pw)
        pw.add(mid_frame, weight=3)

        search_frame = ttk.Frame(mid_frame)
        search_frame.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(search_frame, text="🔎", font=("", 12)).pack(side=tk.LEFT)
        self._choice_query_ent = ttk.Entry(search_frame, font=("", 12))
        self._choice_query_ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._choice_query_ent.bind("<Return>", lambda e: self._choice_go())

        # MCP 工具选择下拉 + 一键调用
        mcp_btn_frame = ttk.Frame(search_frame)
        mcp_btn_frame.pack(side=tk.LEFT, padx=2)
        self._choice_mcp_tool_var = tk.StringVar(value="🏒 A股数据")
        mcp_tool_names = [f"{e} {n}" for e, n, _ in MCP_TOOLS.values()]
        mcp_tool_keys = list(MCP_TOOLS.keys())
        # 映射显示名 → tool_name
        self._choice_mcp_tool_map = dict(zip(mcp_tool_names, mcp_tool_keys))
        mcp_combo = ttk.Combobox(mcp_btn_frame, textvariable=self._choice_mcp_tool_var,
                                 values=mcp_tool_names, width=10, state="readonly",
                                 font=("", 10))
        mcp_combo.pack(side=tk.LEFT)
        ttk.Button(mcp_btn_frame, text="▶ MCP", width=6,
                   command=lambda: self._choice_do_mcp(
                       self._choice_mcp_tool_map.get(self._choice_mcp_tool_var.get(), ""))
                   ).pack(side=tk.LEFT, padx=2)

        ttk.Button(search_frame, text="🧠 AI", width=5,
                    command=lambda: self._choice_do("miaoxiang")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="🏒 涨停", width=6,
                    command=lambda: self._choice_do("zt_pool")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="🐉 龙虎", width=6,
                    command=lambda: self._choice_do("lhb")).pack(side=tk.LEFT, padx=2)

        self._choice_nb = ttk.Notebook(mid_frame)
        self._choice_nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        self._choice_list_tab = ttk.Frame(self._choice_nb)
        self._choice_nb.add(self._choice_list_tab, text="📋 数据列表")

        self._choice_ai_tab = ttk.Frame(self._choice_nb)
        self._choice_nb.add(self._choice_ai_tab, text="🧠 妙想 AI")

        self._choice_tree_frame = ttk.Frame(self._choice_list_tab)
        self._choice_tree_frame.pack(fill=tk.BOTH, expand=True)

        # ═══ 右列: 详情预览 ═══
        right_frame = ttk.Frame(pw, width=430)
        pw.add(right_frame, weight=2)

        ttk.Label(right_frame, text="📖 详情 / 提示",
                  font=("", 11, "bold")).pack(anchor="w", padx=6, pady=4)

        self._choice_detail_text = tk.Text(right_frame, wrap=tk.WORD,
                                           font=("TkDefaultFont", 10),
                                           background="#fff8e1", height=30)
        self._choice_detail_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._choice_detail_text.configure(state=tk.DISABLED)

        # 初始化: 自动加载涨停池
        dlg.after(100, lambda: (
            self._choice_feat_lb.selection_clear(0, tk.END),
            self._choice_feat_lb.selection_set(0),
            self._choice_do("zt_pool")
        ))

    # ── API Key 配置 ──

    def _choice_config_apikey(self, parent):
        """配置妙想 API Key 弹窗"""
        dlg = tk.Toplevel(parent)
        dlg.title("🔑 妙想 API Key 配置")
        dlg.geometry("560x400")
        dlg.transient(parent)
        dlg.grab_set()

        keys = _load_apikey()

        tk.Label(dlg, text="🧠 妙想 AI 查询需要 API Key",
                 font=("", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
        tk.Label(dlg, text="获取方式:\n"
                 "1. 打开 https://choice.eastmoney.com/mcp/\n"
                 "2. 登录后点击「查看 API Key」\n"
                 "3. 复制填入下方 (格式: mkt_xxx...)\n"
                 "💰 免费版每日 300 次, 会员版更多",
                 justify=tk.LEFT, foreground="#666",
                 font=("", 9)).pack(anchor="w", padx=12)

        frame1 = ttk.Frame(dlg)
        frame1.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(frame1, text="妙想 Skills API Key:", width=20).pack(side=tk.LEFT)
        skills_var = tk.StringVar(value=keys.get("skills_apikey", ""))
        ttk.Entry(frame1, textvariable=skills_var, show="*", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        frame2 = ttk.Frame(dlg)
        frame2.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(frame2, text="妙想 MCP API Key:", width=20).pack(side=tk.LEFT)
        mcp_var = tk.StringVar(value=keys.get("mx_apikey", ""))
        ttk.Entry(frame2, textvariable=mcp_var, show="*", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _save():
            s = skills_var.get().strip()
            m = mcp_var.get().strip()
            if s and not s.startswith("mkt_"):
                if not tk.messagebox.askyesno("格式提示",
                    "妙想 Skills API Key 通常以 mkt_ 开头\n"
                    f"你当前输入的是: {s[:20]}...\n\n"
                    "确认保存?"):
                    return
            _save_apikey({"skills_apikey": s, "mx_apikey": m})
            tk.messagebox.showinfo("保存成功", "✅ API Key 已保存\n\n免费版每日 300 次\n打开弹窗右上角会显示「已配置」")
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=12)

        def _test_key():
            s = skills_var.get().strip()
            if not s:
                tk.messagebox.showwarning("提示", "请先粘贴 API Key")
                return
            try:
                r = requests.post(
                    MIAOXIANG_SKILLS_URL,
                    json={"toolQuery": "A股今日成交量"},
                    headers={"Content-Type": "application/json", "apikey": s},
                    timeout=15,
                )
                j = r.json()
                if j.get("success"):
                    tk.messagebox.showinfo("✅ Key 有效", "API Key 验证通过, 妙想 AI 立即可用!")
                else:
                    msg = j.get("message", r.text[:200])
                    tk.messagebox.showerror("❌ Key 无效", f"服务器返回:\n{msg}")
            except Exception as e:
                tk.messagebox.showerror("❌ 网络错误", str(e)[:200])

        ttk.Button(btn_frame, text="🧪 测试 Key", command=_test_key, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="💾 保存", command=_save, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="❌ 取消", command=dlg.destroy, width=10).pack(side=tk.LEFT, padx=6)

    # ── 调度 ──

    def _choice_on_feat_select(self):
        sel = self._choice_feat_lb.curselection()
        if not sel: return
        _, mode = self._CHOICE_FEATURES[sel[0]]
        self._choice_do(mode)

    def _choice_preset(self, tpl: str):
        self._choice_query_ent.delete(0, tk.END)
        self._choice_query_ent.insert(0, tpl)
        self._choice_do("miaoxiang")

    def _choice_go(self):
        q = self._choice_query_ent.get().strip()
        if not q: return
        # 自动识别模式
        if any(k in q for k in ["最新价", "市值", "PE", "财报", "利润", "营收"]):
            self._choice_do("miaoxiang")
        else:
            self._choice_do("miaoxiang")

    def _choice_do(self, mode: str):
        """后台线程"""
        for w in self._choice_tree_frame.winfo_children():
            w.destroy()

        if mode == "miaoxiang":
            query = self._choice_query_ent.get().strip()
            if not query:
                self._choice_status.set("⚠️ 请输入问题")
                self._choice_set_detail("⚠️ 请在搜索框输入问题\n\n示例:\n  宁德时代最新价\n  比亚迪 PE 估值\n  今日涨停股票\n  半导体资金流向")
                return
            self._choice_nb.select(1)
            self._choice_status.set(f"⏳ 妙想 AI 思考: {query}")
            self._choice_set_detail(f"⏳ 正在通过妙想 Skills API 查询: {query}\n\n请稍候...")
        else:
            self._choice_nb.select(0)
            self._choice_status.set(f"⏳ 加载 {mode}...")

        def _bg():
            t0 = time.time()
            result = self._choice_fetch(mode)
            dt = time.time() - t0
            self.root.after(0, lambda: self._choice_render(mode, result, dt))

        threading.Thread(target=_bg, daemon=True).start()

    # ── 数据获取 ──

    def _choice_fetch(self, mode: str) -> dict:
        """不同模式的数据获取"""
        if mode == "miaoxiang":
            return self._choice_query_miaoxiang()
        if ak is None:
            return {"ok": False, "error": "akshare 未安装"}
        try:
            if mode == "zt_pool":
                date = self._choice_date_var.get().strip() or time.strftime("%Y%m%d")
                df = ak.stock_zt_pool_em(date=date)
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "lhb":
                date = self._choice_date_var.get().strip() or time.strftime("%Y%m%d")
                df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "gdp":
                df = ak.macro_china_gdp()
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "cpi":
                df = ak.macro_china_cpi()
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "pmi":
                df = ak.macro_china_pmi()
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "bond_yield":
                df = ak.bond_china_yield(start_date="20240101",
                                          end_date=time.strftime("%Y%m%d"))
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "financial":
                code = self._choice_code_var.get().strip() or "600519"
                df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}
        return {"ok": False, "error": f"未知模式: {mode}"}

    def _choice_query_miaoxiang(self) -> dict:
        """调妙想 Skills API"""
        keys = _load_apikey()
        apikey = (keys.get("skills_apikey") or os.getenv("EASTMONEY_APIKEY", "")).strip()
        query = self._choice_query_ent.get().strip()
        if not query:
            return {"ok": False, "error": "请输入查询问题"}
        if not apikey:
            return {"ok": False, "error": ("⚠️ 需要妙想 API Key\n\n"
                    "1. 点顶栏「🔑 配置 API Key」按钮\n"
                    "2. 打开 https://choice.eastmoney.com/mcp/ 获取\n"
                    "3. 免费版每日 300 次调用\n\n"
                    "💡 无 Key 时可用左列其他 akshare 功能 (涨停/龙虎榜/宏观)")}
        try:
            resp = requests.post(
                MIAOXIANG_SKILLS_URL,
                json={"toolQuery": query},
                headers={"Content-Type": "application/json",
                         "apikey": apikey},
                timeout=60,
            )
            j = resp.json()
            if j.get("success"):
                return {"ok": True, "ai_result": j}
            else:
                return {"ok": False, "error": f"妙想 API 错误: {j.get('message', resp.text[:200])}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    # ── 妙想 MCP (JSON-RPC 2.0) ──

    def _choice_mcp_call(self, tool_name: str, query: str) -> dict:
        """调妙想 MCP tools/call"""
        keys = _load_apikey()
        apikey = (keys.get("mx_apikey") or keys.get("skills_apikey") or "").strip()
        if not apikey:
            return {"ok": False, "error": ("⚠️ 需要妙想 MCP API Key\n\n"
                    "1. 点顶栏「🔑 配置 API Key」按钮\n"
                    "2. 打开 https://choice.eastmoney.com/mcp/ 获取\n"
                    "3. MCP Key 通常以 em_ 开头")}
        try:
            resp = requests.post(
                MIAOXIANG_MCP_URL,
                json={"jsonrpc": "2.0", "id": 1,
                      "method": "tools/call",
                      "params": {"name": tool_name, "arguments": {"query": query}}},
                headers={"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream",
                         "em_api_key": apikey},
                timeout=60,
            )
            if resp.status_code in (401, 403):
                return {"ok": False, "error": f"❌ API Key 无效 (HTTP {resp.status_code})\n\n请重新获取: https://choice.eastmoney.com/mcp/"}
            j = resp.json()
            result = j.get("result") or {}
            if result.get("isError"):
                return {"ok": False, "error": json.dumps(result, ensure_ascii=False)[:500]}
            return {"ok": True, "mcp_result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    def _choice_mcp_list_tools(self) -> dict:
        """调妙想 MCP tools/list 获取所有可用工具"""
        keys = _load_apikey()
        apikey = (keys.get("mx_apikey") or keys.get("skills_apikey") or "").strip()
        if not apikey:
            return {"ok": False, "error": "需要 MCP API Key"}
        try:
            resp = requests.post(
                MIAOXIANG_MCP_URL,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream",
                         "em_api_key": apikey},
                timeout=30,
            )
            j = resp.json()
            tools = j.get("result", {}).get("tools", [])
            return {"ok": True, "tools": tools}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def _choice_mcp_parse_result(self, mcp_result: dict) -> list:
        """解析 MCP tools/call 返回 → [(sheet_name, columns, items)]
        同时识别业务提示(message-only, 如积分耗尽)"""
        sheets = []
        content = mcp_result.get("content") or []
        for c in content:
            if c.get("type") == "text":
                try:
                    inner = json.loads(c["text"])
                except Exception:
                    sheets.append(("📝 原始文本", [], [[c["text"]]]))
                    continue
                # 业务提示: 只有 message 没有 data (如积分耗尽)
                if "message" in inner and "data" not in inner:
                    msg = inner["message"]
                    sheets.append(("⚠️ 提示", ["消息"], [[msg]]))
                    continue
                data_list = inner.get("data") or []
                for d in data_list:
                    sheet_name = d.get("name") or d.get("sheetName") or "数据"
                    cols = d.get("columns") or []
                    items = d.get("items") or []
                    sheets.append((sheet_name, cols, items))
                meta = inner.get("meta") or {}
                if meta.get("jumpUrlList"):
                    for ju in meta["jumpUrlList"]:
                        url = ju.get("choiceUrl", "")
                        if url:
                            sheets.append((f"🔗 {ju.get('typeName','跳转')}", ["URL"], [[url]]))
        return sheets

    def _choice_do_mcp(self, tool_name: str):
        """MCP 工具一键查询"""
        query = self._choice_query_ent.get().strip()
        # 如果用户没输入, 根据工具给一个默认示例
        if not query:
            # 从模板里找一个默认值
            for cat, tpls in MCP_TEMPLATES.items():
                for t, q in tpls:
                    if t == tool_name:
                        query = q
                        break
                if query: break
        if not query:
            tk.messagebox.showinfo("提示", f"请输入 {MCP_TOOLS.get(tool_name, ('','',''))[1]} 查询内容\n例如: 贵州茅台最新市值")
            return

        emoji, label, _ = MCP_TOOLS.get(tool_name, ("🧠", tool_name, ""))
        self._choice_status.set(f"⏳ MCP {label}: {query[:40]}...")
        self._choice_set_detail(f"⏳ 正在通过妙想 MCP 调用 {tool_name}\n\n查询: {query}\n\n请稍候...")

        def _run():
            t0 = time.time()
            result = self._choice_mcp_call(tool_name, query)
            dt = time.time() - t0
            dlg = self._choice_nb.winfo_toplevel()
            dlg.after(0, lambda: self._choice_render_mcp(result, dt, tool_name))
        threading.Thread(target=_run, daemon=True).start()

    def _choice_render_mcp(self, result: dict, dt: float, tool_name: str):
        """MCP 结果渲染 → 数据列表 Tab"""
        self._choice_nb.select(0)
        for w in self._choice_tree_frame.winfo_children():
            w.destroy()

        if not result.get("ok"):
            self._choice_status.set(f"❌ MCP 失败: {result.get('error','?')[:50]}")
            self._choice_set_detail(f"❌ MCP 调用失败\n\n{result.get('error', '未知错误')}")
            return

        sheets = self._choice_mcp_parse_result(result.get("mcp_result", {}))
        if not sheets:
            self._choice_status.set(f"⚠️ MCP 返回空数据 ({dt:.1f}s)")
            self._choice_set_detail(json.dumps(result.get("mcp_result", {}), ensure_ascii=False, indent=2)[:1500])
            return

        # 用 Notebook 展示多 sheet
        sheet_nb = ttk.Notebook(self._choice_tree_frame)
        sheet_nb.pack(fill=tk.BOTH, expand=True)

        for sheet_name, cols, items in sheets[:8]:  # 最多 8 个 sheet
            sheet_frame = ttk.Frame(sheet_nb)
            tab_label = sheet_name[:25] + ("..." if len(sheet_name) > 25 else "")
            sheet_nb.add(sheet_frame, text=tab_label)

            if not cols or not items:
                ttk.Label(sheet_frame, text="📭 无数据", foreground="gray").pack(pady=40)
                continue

            # 创建 Treeview
            tree_cols = [str(c) for c in cols]
            tv = ttk.Treeview(sheet_frame, columns=tree_cols, show="headings",
                              height=min(20, len(items)))
            # 自适应列宽: 取列头 + 数据每行最长内容, 按中文字符 14px / 英文 8px 估算
            def _col_width(col_idx):
                # 列头宽度
                header = str(cols[col_idx] if col_idx < len(cols) else "")
                # 数据中该列最长
                max_cell = header
                for row in items:
                    if col_idx < len(row):
                        cell = str(row[col_idx])[:60] if row[col_idx] else ""
                        if len(cell) > len(max_cell):
                            max_cell = cell
                # 中文按 14px/字, 英文按 8px/字
                w = 0
                for ch in max_cell:
                    w += 14 if ord(ch) > 127 else 8
                return max(70, min(280, w + 18))  # 最少 70, 最多 280, 加 18px padding
            widths = [_col_width(i) for i in range(len(tree_cols))]
            for h, w in zip(tree_cols, widths):
                tv.heading(h, text=h)
                tv.column(h, width=w, anchor="w", minwidth=60, stretch=True)
            # 允许横向滚动 (防止列太多时被挤没)
            hsb = ttk.Scrollbar(sheet_frame, orient=tk.HORIZONTAL, command=tv.xview)
            tv.configure(xscrollcommand=hsb.set)
            hsb.pack(side=tk.BOTTOM, fill=tk.X)

            for row in items:
                vals = []
                for i, v in enumerate(row):
                    if i < len(tree_cols):
                        vals.append(str(v)[:80] if v else "")
                tv.insert("", tk.END, values=vals)

            vsb = ttk.Scrollbar(sheet_frame, orient=tk.VERTICAL, command=tv.yview)
            tv.configure(yscrollcommand=vsb.set)
            tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

        emoji, label, _ = MCP_TOOLS.get(tool_name, ("🧠", tool_name, ""))
        self._choice_status.set(f"✅ MCP {label}: {len(sheets)} 张表 ({dt:.1f}s)")
        self._choice_set_detail(
            f"✅ 妙想 MCP 查询完成\n\n"
            f"🔧 工具: {tool_name}\n"
            f"📊 返回: {len(sheets)} 张数据表\n"
            f"⏱️ 耗时: {dt:.1f}s\n\n"
            f"💡 提示: 点下方 Sheet 切换查看不同表格")

    # ── 渲染 ──

    def _choice_render(self, mode: str, result: dict, dt: float):
        if mode == "miaoxiang":
            self._choice_render_ai(result, dt)
            return

        if not result.get("ok"):
            self._choice_status.set(f"❌ 失败: {result.get('error', '?')[:60]}")
            self._choice_set_detail(f"❌ 加载失败\n\n{result.get('error', '未知错误')}\n\n"
                                     f"💡 建议:\n"
                                     f"• 检查东方财富是否被限流 (稍后重试)\n"
                                     f"• 确认 akshare 版本最新\n"
                                     f"• 妙想 AI 查询需先配置 API Key")
            return

        data = result.get("data") or []
        headers = result.get("headers") or []

        # 智能选列: 最多 8 列
        display_headers = self._choice_pick_headers(headers, mode)

        tree = ttk.Treeview(self._choice_tree_frame, columns=display_headers,
                            show="headings", height=min(28, len(data)))
        widths = self._choice_auto_width(display_headers)
        for h, w in zip(display_headers, widths):
            tree.heading(h, text=h)
            anchor = "center" if any(x in h for x in ("序号", "涨跌", "涨幅", "市值", "价格", "量", "额", "率")) else "w"
            tree.column(h, width=w, anchor=anchor)

        # 标签
        if mode == "zt_pool":
            tree.tag_configure("zt", background="#ffebee", foreground="#c62828")
        elif mode == "lhb":
            tree.tag_configure("buy", background="#ffebee", foreground="#c62828")
            tree.tag_configure("sell", background="#e8f5e9", foreground="#2e7d32")

        for i, rec in enumerate(data):
            vals = []
            for h in display_headers:
                v = rec.get(h, "")
                if isinstance(v, float):
                    vals.append(f"{v:.2f}")
                else:
                    vals.append(str(v)[:22] if v else "")
            tag = ""
            if mode == "zt_pool":
                tag = "zt"
            elif mode == "lhb" and len(rec) > 3:
                # 龙虎榜净买
                for k in ("净买入额", "净买额", "净买入"):
                    if k in rec and isinstance(rec[k], (int, float)):
                        tag = "buy" if rec[k] >= 0 else "sell"
                        break
            tree.insert("", tk.END, values=vals, tags=(tag,) if tag else ())

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(self._choice_tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(data):
                self._choice_show_detail(data[idx], mode)

        tree.bind("<<TreeviewSelect>>", _on_select)

        self._choice_status.set(f"✅ {mode}: {len(data)} 条 ({dt:.1f}s)")

    def _choice_render_ai(self, result: dict, dt: float):
        """妙想 AI 结果渲染"""
        self._choice_nb.select(1)
        for w in self._choice_ai_tab.winfo_children():
            w.destroy()

        if not result.get("ok"):
            self._choice_status.set("❌ AI 查询失败")
            self._choice_set_detail(result.get("error", "未知错误"))
            return

        j = result.get("ai_result") or {}
        txt = tk.Text(self._choice_ai_tab, wrap=tk.WORD, font=("", 11),
                       background="#fff3e0")
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # 解包妙想 Skills 返回
        rendered = self._choice_format_miaoxiang_resp(j)
        txt.insert("1.0", f"🧠 妙想 AI 查询结果\n\n{'='*40}\n\n{rendered}")
        try: self._apply_hyperlinks_to_text_widget(txt)
        except Exception: pass
        txt.configure(state=tk.DISABLED)

        self._choice_status.set(f"✅ 妙想 AI 完成 ({dt:.1f}s)")
        self._choice_set_detail(f"📊 妙想 AI 返回\n\n耗时: {dt:.1f}s\n\n原始 JSON 已在上方展示")

    def _choice_format_miaoxiang_resp(self, j: dict) -> str:
        """妙想 Skills 返回格式化"""
        out = []
        data = j.get("data") or {}

        # 表格数据
        tables = data.get("dataTableDTOList") or []
        for t in tables:
            title = t.get("title", "")
            if title:
                out.append(f"📌 {title}")
                out.append("─" * 40)
            name_map = t.get("nameMap") or {}
            order = t.get("indicatorOrder") or []
            table = t.get("table") or {}
            head = table.get("headName") or table.get("headNameSub") or []
            for h in head[:8]:
                out.append(f"  📎 {h}")
            # 指标列
            for col in order[:6]:
                cn = name_map.get(col, col)
                vals = table.get(col, [])[:5]
                out.append(f"    {cn}: {', '.join(str(v) for v in vals)}")
            out.append("")

        # 文本回复
        reply = data.get("replyText") or data.get("text") or ""
        if reply:
            out.append("💬 文本回复:")
            out.append(reply[:2000])

        if not out:
            out.append(json.dumps(j, ensure_ascii=False, indent=2)[:3000])

        return "\n".join(out)

    # ── 详情 ──

    def _choice_show_detail(self, rec: dict, mode: str):
        lines = [f"📊 详情 (mode={mode})", "─" * 40]
        for k, v in rec.items():
            if v is None or v == "": continue
            s = str(v)
            if len(s) > 120: s = s[:120] + "..."
            lines.append(f"  {k}: {s}")
        self._choice_set_detail("\n".join(lines[:60]))

    def _choice_set_detail(self, text: str):
        self._choice_detail_text.configure(state=tk.NORMAL)
        self._choice_detail_text.delete("1.0", tk.END)
        self._choice_detail_text.insert("1.0", text)
        try: self._apply_hyperlinks_to_text_widget(self._choice_detail_text)
        except Exception: pass
        self._choice_detail_text.configure(state=tk.DISABLED)

    # ── 工具 ──

    def _choice_pick_headers(self, headers: list, mode: str) -> list:
        """根据模式选关键列"""
        if not headers: return []
        # 各模式关键列
        key_cols = {
            "zt_pool": ["序号", "代码", "名称", "涨跌幅", "最新价", "成交额", "封板资金", "换手率", "连板数"],
            "lhb": ["序号", "代码", "名称", "收盘价", "涨跌幅", "成交额", "净买入额", "买入总额", "卖出总额"],
            "gdp": ["季度", "GDP同比增长", "GDP环比增长", "GDP累计同比增长"],
            "cpi": ["月份", "全国-当月", "全国-同比增长", "全国-环比增长"],
            "pmi": ["月份", "制造业PMI", "非制造业PMI"],
            "bond_yield": ["曲线名称", "日期", "1年", "3年", "5年", "10年"],
            "financial": ["报告期", "净利润", "净利润同比增长率", "营业总收入", "营业总收入同比增长率", "基本每股收益", "ROE"],
        }
        wanted = key_cols.get(mode, [])
        picked = [h for h in wanted if h in headers]
        if len(picked) < 3:
            picked = headers[:8]
        return picked[:9]

    def _choice_auto_width(self, headers: list) -> list:
        widths = {"序号": 35, "代码": 70, "名称": 130, "日期": 80,
                  "收盘价": 70, "最新价": 70, "涨跌幅": 70, "成交额": 90,
                  "换手率": 70, "封板资金": 90, "连板数": 60, "净买入额": 90,
                  "买入总额": 90, "卖出总额": 90}
        return [widths.get(h, 100) for h in headers]

    # ═══════════════════════════════════════════════════════════
    # 🚀 机构大幅增持 (主界面快捷入口)
    # ═══════════════════════════════════════════════════════════

    # 3 个机构增持预设查询
    _INST_BUY_PRESETS = [
        ("机构数增幅TOP",
         "2026中报机构数量较2025年报增长超过50%的股票，按机构增长率排序，显示机构持股家数环比增长率、上期机构家数、本期机构家数、净利润增长率、总市值"),
        ("北向+机构双增TOP",
         "北向资金+机构持仓同时大幅增加的股票TOP30，显示沪深股通净买入额、机构持股较上期变化、涨跌幅、市盈率、总市值"),
        ("机构占比提升TOP",
         "机构持仓占总股本比例上升最快的A股TOP30，显示机构持股占比变化、机构数量变化、累计持股变化、净利润增长率"),
    ]

    def _show_institutional_buy(self):
        """🚀 机构大幅增持 —— 左右分栏弹窗 (左扫描 / 右详情报告)"""
        dlg = tk.Toplevel(getattr(self, "root", None))
        dlg.title("🚀 机构大幅增持扫描")
        dlg.geometry("1420x780")
        dlg.transient(getattr(self, "root", None))

        # 顶栏
        top = ttk.Frame(dlg)
        top.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(top, text="🚀 机构大幅增持扫描",
                 font=("", 14, "bold")).pack(side=tk.LEFT)
        self._inst_buy_status = tk.StringVar(value="⏳ 加载中...")
        ttk.Label(top, textvariable=self._inst_buy_status,
                  foreground="blue").pack(side=tk.LEFT, padx=12)

        # 主分栏 PanedWindow
        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # ═══ 左栏: 扫描 + 结果 ═══
        left = ttk.Frame(pw, width=700)
        pw.add(left, weight=3)

        # 扫描按钮 (MCP)
        scan_frame = ttk.LabelFrame(left, text="🔍 MCP 扫描 (需积分)", padding=6)
        scan_frame.pack(fill=tk.X, padx=6, pady=4)
        for i, (label, q) in enumerate(self._INST_BUY_PRESETS):
            btn = ttk.Button(scan_frame, text=f"🚀 {label}", width=16,
                             command=lambda qq=q: self._run_inst_buy_scan(qq))
            btn.grid(row=0, column=i, padx=4, pady=2)

        # AKShare 免费兜底按钮
        ak_frame = ttk.LabelFrame(left, text="🆓 AKShare 免费兜底 (无积分也能用)", padding=6)
        ak_frame.pack(fill=tk.X, padx=6, pady=4)
        for i, (label, hint, mode) in enumerate(self._INST_AK_PRESETS):
            btn = ttk.Button(ak_frame, text=f"🆓 {label}", width=18,
                             command=lambda m=mode: self._run_ak_scan(m))
            btn.grid(row=i // 2, column=i % 2, padx=4, pady=2, sticky="ew")
        ttk.Button(ak_frame, text="📋 Choice面板",
                   command=lambda: (dlg.destroy(), self._show_choice_dialog())
                   ).grid(row=0, column=2, rowspan=1, padx=4, pady=2)

        # 结果 Notebook
        tk.Label(left, text="📊 扫描结果 (双击行 → 右栏展开详情)",
                 font=("", 10, "bold")).pack(anchor="w", padx=8, pady=(4, 2))
        self._inst_buy_nb = ttk.Notebook(left)
        self._inst_buy_nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        # ═══ 右栏: 详情报告面板 ═══
        right = ttk.Frame(pw, width=620)
        pw.add(right, weight=2)

        tk.Label(right, text="📋 详情报告",
                 font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(4, 2))
        self._inst_detail_nb = ttk.Notebook(right)
        self._inst_detail_nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        # 两个 tab: 机构持仓历史 / 资讯研报
        self._inst_holding_tab = ttk.Frame(self._inst_detail_nb)
        self._inst_detail_nb.add(self._inst_holding_tab, text="🏒 机构持仓历史")
        self._inst_news_tab = ttk.Frame(self._inst_detail_nb)
        self._inst_detail_nb.add(self._inst_news_tab, text="📰 资讯研报")

        # 空状态提示
        tk.Label(self._inst_holding_tab,
                 text="👈 双击左侧表格任一行\n\n自动展开该股票的机构持仓历史",
                 foreground="gray", font=("", 11), justify="center"
                 ).pack(expand=True)
        tk.Label(self._inst_news_tab,
                 text="👈 双击左侧表格任一行\n\n自动加载该股票的资讯研报",
                 foreground="gray", font=("", 11), justify="center"
                 ).pack(expand=True)

        # 保存当前股票代码/名称, 供双击使用
        self._inst_buy_dlg = dlg
        self._inst_current_stock = {"code": "", "name": ""}

        dlg.after(300, lambda: self._run_inst_buy_scan(
            self._INST_BUY_PRESETS[0][1]))

    def _run_inst_buy_scan(self, query: str, parent=None):
        """后台线程跑机构增持扫描"""
        # 清空旧结果
        for w in self._inst_buy_nb.winfo_children():
            w.destroy()

        self._inst_buy_status.set(f"⏳ 扫描中: {query[:50]}...")
        dlg = parent or getattr(self, "_inst_buy_dlg", None)

        def _run():
            t0 = time.time()
            result = self._choice_mcp_call("mx_stocks_screener", query)
            dt = time.time() - t0
            if dlg and dlg.winfo_exists():
                dlg.after(0, lambda: self._render_inst_buy_result(result, dt, dlg))
        threading.Thread(target=_run, daemon=True).start()

    def _render_inst_buy_result(self, result: dict, dt: float, dlg):
        """渲染机构增持扫描结果"""
        if not result.get("ok"):
            self._inst_buy_status.set(f"❌ 扫描失败: {result.get('error','?')[:50]}")
            return

        sheets = self._choice_mcp_parse_result(result.get("mcp_result", {}))
        if not sheets:
            self._inst_buy_status.set(f"⚠️ 返回空数据 ({dt:.1f}s)")
            return

        # 检测业务提示 (如积分耗尽)
        for sname, _, sitems in sheets:
            if "提示" in sname and sitems:
                msg = str(sitems[0][0]) if sitems[0] else ""
                if "积分" in msg:
                    self._inst_buy_status.set("💰 MCP 积分用完啦 → https://ai.eastmoney.com/work 购买")
                else:
                    self._inst_buy_status.set(f"⚠️ {msg[:40]}")
                break
        else:
            self._inst_buy_status.set(f"✅ 扫描中 ({dt:.1f}s)...")

        for sheet_name, cols, items in sheets[:5]:
            sheet_frame = ttk.Frame(self._inst_buy_nb)
            tab_label = sheet_name[:30] + ("..." if len(sheet_name) > 30 else "")
            self._inst_buy_nb.add(sheet_frame, text=tab_label)

            if not cols or not items:
                ttk.Label(sheet_frame, text="📭 无数据", foreground="gray").pack(pady=40)
                continue

            tree_cols = [str(c) for c in cols]
            tv = ttk.Treeview(sheet_frame, columns=tree_cols, show="headings",
                              height=min(25, len(items)))
            # 自适应列宽
            def _cw(idx):
                max_cell = str(cols[idx] if idx < len(cols) else "")
                for row in items:
                    if idx < len(row):
                        cell = str(row[idx])[:60] if row[idx] else ""
                        if len(cell) > len(max_cell):
                            max_cell = cell
                w = sum(14 if ord(ch) > 127 else 8 for ch in max_cell)
                return max(70, min(280, w + 18))
            widths = [_cw(i) for i in range(len(tree_cols))]
            for h, w in zip(tree_cols, widths):
                tv.heading(h, text=h)
                tv.column(h, width=w, anchor="w", minwidth=60, stretch=True)

            for row in items:
                vals = [str(v)[:80] if v else "" for v in row[:len(tree_cols)]]
                tv.insert("", tk.END, values=vals)

            vsb = ttk.Scrollbar(sheet_frame, orient=tk.VERTICAL, command=tv.yview)
            hsb = ttk.Scrollbar(sheet_frame, orient=tk.HORIZONTAL, command=tv.xview)
            tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            hsb.pack(side=tk.BOTTOM, fill=tk.X)

            # 选中/双击行 → 右栏展开该股票详情报告
            def _on_select(event=None, _tv=tv):
                sel = _tv.selection()
                if not sel: return
                vals = _tv.item(sel[0], "values")
                # 列顺序: 序号、代码、名称, 跳过序号列
                code = str(vals[1]) if len(vals) > 1 else ""
                name = str(vals[2]) if len(vals) > 2 else ""
                if code and name:
                    self._inst_current_stock = {"code": code, "name": name}
                    self._inst_buy_status.set(f"🔄 加载 {name}({code}) 详情...")
                    self._load_inst_detail(code, name)
            tv.bind("<<TreeviewSelect>>", _on_select)
            tv.bind("<Double-1>", _on_select)

        self._inst_buy_status.set(
            f"✅ 扫描完成: {sum(len(i) for _, _, i in sheets)} 条记录 / {len(sheets)} 张表 ({dt:.1f}s)")

    def _load_inst_detail(self, code: str, name: str):
        """右栏加载机构持仓历史 + 资讯研报 (两条 MCP 并行)"""
        # 清空右栏
        for w in self._inst_holding_tab.winfo_children():
            w.destroy()
        for w in self._inst_news_tab.winfo_children():
            w.destroy()

        tk.Label(self._inst_holding_tab, text=f"⏳ {name}({code}) 机构持仓加载中...",
                 foreground="gray").pack(pady=40)
        tk.Label(self._inst_news_tab, text=f"⏳ {name} 资讯研报加载中...",
                 foreground="gray").pack(pady=40)

        holding_q = f"{name}({code}) 机构持仓历史变化、持股机构家数、累计持股数量、基金/社保/其他机构分类"
        news_q = f"{name} 最新券商研报、评级观点、目标价、行业资讯"

        def _run():
            import concurrent.futures
            t0 = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                f_hold = pool.submit(self._choice_mcp_call, "mx_ashare_finance_data", holding_q)
                f_news = pool.submit(self._choice_mcp_call, "mx_finance_search_news", news_q)
                holding_result = f_hold.result(timeout=60)
                news_result = f_news.result(timeout=60)
            dt = time.time() - t0
            if self._inst_buy_dlg and self._inst_buy_dlg.winfo_exists():
                self._inst_buy_dlg.after(0, lambda: (
                    self._render_inst_holding(code, name, holding_result),
                    self._render_inst_news(code, name, news_result, dt),
                ))
        threading.Thread(target=_run, daemon=True).start()

    def _render_inst_holding(self, code, name, result):
        """渲染机构持仓历史到右栏"""
        for w in self._inst_holding_tab.winfo_children():
            w.destroy()

        header = tk.Frame(self._inst_holding_tab)
        header.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(header, text=f"🏒 {name}({code}) 机构持仓历史",
                 font=("", 12, "bold")).pack(side=tk.LEFT)

        if not result.get("ok"):
            tk.Label(self._inst_holding_tab,
                     text=f"❌ {result.get('error','加载失败')}",
                     foreground="red").pack(pady=20)
            return

        sheets = self._choice_mcp_parse_result(result.get("mcp_result", {}))
        if not sheets:
            tk.Label(self._inst_holding_tab, text="📭 无数据",
                     foreground="gray").pack(pady=20)
            return

        # 多 sheet 用子 Notebook
        sub_nb = ttk.Notebook(self._inst_holding_tab)
        sub_nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        for sheet_name, cols, items in sheets[:8]:
            frame = ttk.Frame(sub_nb)
            label = sheet_name[:28] + ("..." if len(sheet_name) > 28 else "")
            sub_nb.add(frame, text=label)

            if not cols or not items:
                ttk.Label(frame, text="📭 空", foreground="gray").pack(pady=20)
                continue

            tree_cols = [str(c) for c in cols]
            tv = ttk.Treeview(frame, columns=tree_cols, show="headings",
                              height=min(15, len(items)))
            def _cw(idx, _cols=cols, _items=items):
                mc = str(_cols[idx] if idx < len(_cols) else "")
                for row in _items:
                    if idx < len(row):
                        cell = str(row[idx])[:60] if row[idx] else ""
                        if len(cell) > len(mc): mc = cell
                w = sum(14 if ord(ch) > 127 else 8 for ch in mc)
                return max(60, min(260, w + 14))
            for h, w in zip(tree_cols, [_cw(i) for i in range(len(tree_cols))]):
                tv.heading(h, text=h)
                tv.column(h, width=w, anchor="w", minwidth=50)
            for row in items:
                vals = [str(v)[:80] if v else "" for v in row[:len(tree_cols)]]
                tv.insert("", tk.END, values=vals)

            vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tv.yview)
            hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tv.xview)
            tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            hsb.pack(side=tk.BOTTOM, fill=tk.X)

    def _render_inst_news(self, code, name, result, dt=0):
        """渲染资讯研报到右栏"""
        for w in self._inst_news_tab.winfo_children():
            w.destroy()

        header = tk.Frame(self._inst_news_tab)
        header.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(header, text=f"📰 {name} 资讯研报",
                 font=("", 12, "bold")).pack(side=tk.LEFT)
        if dt:
            tk.Label(header, text=f"  ({dt:.1f}s)",
                     foreground="gray").pack(side=tk.LEFT)

        if not result.get("ok"):
            tk.Label(self._inst_news_tab,
                     text=f"❌ {result.get('error','加载失败')}",
                     foreground="red").pack(pady=20)
            return

        sheets = self._choice_mcp_parse_result(result.get("mcp_result", {}))
        if not sheets:
            tk.Label(self._inst_news_tab, text="📭 无资讯数据",
                     foreground="gray").pack(pady=20)
            return

        sub_nb = ttk.Notebook(self._inst_news_tab)
        sub_nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        for sheet_name, cols, items in sheets[:5]:
            frame = ttk.Frame(sub_nb)
            label = sheet_name[:28] + ("..." if len(sheet_name) > 28 else "")
            sub_nb.add(frame, text=label)

            if not cols or not items:
                ttk.Label(frame, text="📭 空", foreground="gray").pack(pady=20)
                continue

            tree_cols = [str(c) for c in cols]
            tv = ttk.Treeview(frame, columns=tree_cols, show="headings",
                              height=min(18, len(items)))
            def _cw2(idx, _cols=cols, _items=items):
                mc = str(_cols[idx] if idx < len(_cols) else "")
                for row in _items:
                    if idx < len(row):
                        cell = str(row[idx])[:80] if row[idx] else ""
                        if len(cell) > len(mc): mc = cell
                w = sum(14 if ord(ch) > 127 else 8 for ch in mc)
                return max(60, min(300, w + 14))
            for h, w in zip(tree_cols, [_cw2(i) for i in range(len(tree_cols))]):
                tv.heading(h, text=h)
                tv.column(h, width=w, anchor="w", minwidth=50)
            for row in items:
                vals = [str(v)[:100] if v else "" for v in row[:len(tree_cols)]]
                tv.insert("", tk.END, values=vals)

            vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tv.yview)
            hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tv.xview)
            tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self._inst_buy_status.set(
            f"✅ 已加载 {name}({code}): {len(sheets)} 张资讯表")

    # ═══════════════════════════════════════════════════════════
    # 🔄 AKShare 兜底扫描 (MCP 积分用完时的免费替代)
    # ═══════════════════════════════════════════════════════════

    _INST_AK_PRESETS = [
        ("基金重仓TOP", "🔄 免费 AKShare", "stock_report_fund_hold"),
        ("北向持续买入TOP", "🔄 免费 AKShare", "hsgt_recent_buy"),
        ("机构增持股(股东户数降)", "🔄 免费 AKShare", "holder_count_down"),
    ]

    def _run_ak_scan(self, ak_mode: str):
        """AKShare 兜底扫描 —— 不依赖妙想 MCP"""
        for w in self._inst_buy_nb.winfo_children():
            w.destroy()
        self._inst_buy_status.set(f"⏳ AKShare {ak_mode} 扫描中...")

        def _run():
            import akshare as ak
            import pandas as pd
            t0 = time.time()
            result = {"ok": False, "sheets": [], "error": ""}
            try:
                if ak_mode == "stock_report_fund_hold":
                    # 基金重仓TOP — 按持有基金家数排序
                    import datetime
                    date_str = datetime.datetime.now().strftime("%Y%m%d")
                    # 尝试最近 4 个季度的报告期
                    for offset in [0, 90, 180, 270]:
                        dt = datetime.datetime.now() - datetime.timedelta(days=offset)
                        ds = dt.strftime("%Y") + ("0930" if dt.month >= 9 else "0630" if dt.month >= 6 else "0331" if dt.month >= 3 else "1231")
                        try:
                            df = ak.stock_report_fund_hold(date=ds)
                            if df is not None and len(df) > 0:
                                date_str = ds
                                break
                        except Exception:
                            continue
                    if df is None or len(df) == 0:
                        df = ak.stock_report_fund_hold(date="20251231")
                    # 转成表格
                    cols = list(df.columns)
                    items = df.values.tolist()[:50]  # TOP50
                    result["ok"] = True
                    result["sheets"] = [(f"基金重仓TOP50 ({date_str})", cols, items)]

                elif ak_mode == "hsgt_recent_buy":
                    # 北向持续买入 — 逐只查太耗时, 用历史汇总 + 单只 top
                    # 方案: 拉沪股通+深股通最近 30 天数据, 找出累计净流入>0 的日期占比
                    frames = []
                    for sym in ["沪股通", "深股通"]:
                        try:
                            df = ak.stock_hsgt_hist_em(symbol=sym)
                            if df is not None and len(df) > 0:
                                df = df.tail(60).copy()
                                df["板块"] = sym
                                frames.append(df[["日期", "当日成交净买额", "历史累计净买额", "板块"]])
                        except Exception:
                            pass
                    if frames:
                        import pandas as pd
                        combined = pd.concat(frames, ignore_index=True)
                        cols = list(combined.columns)
                        items = combined.values.tolist()
                        result["ok"] = True
                        result["sheets"] = [(f"北向资金近60日净流入 ({len(combined)}行)", cols, items)]
                    else:
                        result["error"] = "北向数据获取失败"

                elif ak_mode == "holder_count_down":
                    # 股东户数下降TOP = 免费版机构增持代理指标
                    # stock_circulate_stock_holder 逐只查, 批量会慢 → 用实时行情前 100 只抽样
                    import pandas as pd
                    spot = ak.stock_zh_a_spot_em()
                    spot = spot.head(100)
                    results = []
                    for _, row in spot.iterrows():
                        code = str(row["代码"])
                        name = str(row["名称"])
                        try:
                            df = ak.stock_circulate_stock_holder(symbol=code)
                            if df is not None and len(df) >= 2:
                                dates = df["截止日期"].tolist()[:2]
                                counts = df["股东户数"].tolist()[:2]
                                if len(counts) >= 2 and counts[1] and counts[0]:
                                    try:
                                        pct = (float(counts[0]) - float(counts[1])) / float(counts[1]) * 100
                                        results.append({
                                            "代码": code, "名称": name,
                                            "最新价": row.get("最新价", ""),
                                            "涨跌幅": row.get("涨跌幅", ""),
                                            "上上期截止": dates[0], "上上期户数": counts[0],
                                            "上期截止": dates[1], "上期户数": counts[1],
                                            "户数变化%": round(pct, 2),
                                        })
                                    except (ValueError, ZeroDivisionError):
                                        pass
                        except Exception:
                            continue
                        if len(results) >= 30:
                            break
                    results.sort(key=lambda x: x["户数变化%"], reverse=True)
                    if results:
                        cols = list(results[0].keys())
                        items = [[r[c] for c in cols] for r in results]
                        result["ok"] = True
                        result["sheets"] = [(f"股东户数下降TOP ({len(results)}只, 抽样100)", cols, items)]
                    else:
                        result["error"] = "股东户数数据获取失败"

            except Exception as e:
                result["error"] = f"AKShare 异常: {str(e)[:200]}"

            dt = time.time() - t0
            if self._inst_buy_dlg and self._inst_buy_dlg.winfo_exists():
                self._inst_buy_dlg.after(0, lambda: self._render_ak_scan_result(result, dt, ak_mode))
        threading.Thread(target=_run, daemon=True).start()

    def _render_ak_scan_result(self, result: dict, dt: float, ak_mode: str):
        """渲染 AKShare 扫描结果到左栏"""
        if not result.get("ok"):
            self._inst_buy_status.set(f"❌ {result.get('error','AKShare 失败')[:60]}")
            return

        sheets = result.get("sheets", [])
        if not sheets:
            self._inst_buy_status.set(f"⚠️ AKShare 返回空 ({dt:.1f}s)")
            return

        for sheet_name, cols, items in sheets[:5]:
            sheet_frame = ttk.Frame(self._inst_buy_nb)
            tab_label = sheet_name[:30] + ("..." if len(sheet_name) > 30 else "")
            self._inst_buy_nb.add(sheet_frame, text=tab_label)

            if not cols or not items:
                ttk.Label(sheet_frame, text="📭 无数据", foreground="gray").pack(pady=40)
                continue

            tree_cols = [str(c) for c in cols]
            tv = ttk.Treeview(sheet_frame, columns=tree_cols, show="headings",
                              height=min(25, len(items)))

            def _cw(idx, _cols=cols, _items=items):
                mc = str(_cols[idx] if idx < len(_cols) else "")
                for row in _items:
                    if idx < len(row):
                        cell = str(row[idx])[:80] if row[idx] else ""
                        if len(cell) > len(mc): mc = cell
                w = sum(14 if ord(ch) > 127 else 8 for ch in mc)
                return max(60, min(260, w + 14))

            for h, w in zip(tree_cols, [_cw(i) for i in range(len(tree_cols))]):
                tv.heading(h, text=h)
                tv.column(h, width=w, anchor="w", minwidth=50, stretch=True)

            for row in items:
                vals = [str(v)[:100] if v else "" for v in row[:len(tree_cols)]]
                tv.insert("", tk.END, values=vals)

            vsb = ttk.Scrollbar(sheet_frame, orient=tk.VERTICAL, command=tv.yview)
            hsb = ttk.Scrollbar(sheet_frame, orient=tk.HORIZONTAL, command=tv.xview)
            tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            hsb.pack(side=tk.BOTTOM, fill=tk.X)

            # 双击行 → 右栏加载 AKShare 详情
            def _on_select(event=None, _tv=tv):
                sel = _tv.selection()
                if not sel: return
                vals = _tv.item(sel[0], "values")
                # 找到 代码 和 名称 列
                code, name = "", ""
                for i, c in enumerate(cols):
                    if "代码" in c and i < len(vals): code = str(vals[i])
                    if "名称" in c and i < len(vals): name = str(vals[i])
                if code and name:
                    self._inst_current_stock = {"code": code, "name": name}
                    self._inst_buy_status.set(f"🔄 加载 {name}({code}) AKShare 详情...")
                    self._load_ak_detail(code, name)
            tv.bind("<<TreeviewSelect>>", _on_select)
            tv.bind("<Double-1>", _on_select)

        total = sum(len(i) for _, _, i in sheets)
        self._inst_buy_status.set(
            f"✅ AKShare 免费数据: {total} 条 / {len(sheets)} 张表 ({dt:.1f}s)")

    def _load_ak_detail(self, code: str, name: str):
        """右栏用 AKShare 加载个股机构/股东/北向详情 (不依赖 MCP)"""
        for w in self._inst_holding_tab.winfo_children(): w.destroy()
        for w in self._inst_news_tab.winfo_children(): w.destroy()

        import akshare as ak

        tk.Label(self._inst_holding_tab, text=f"⏳ {name}({code}) AKShare 机构/股东加载中...",
                 foreground="gray").pack(pady=40)

        # 并行拉: 股东户数 + 十大股东 + 基金持仓 + 北向持股
        def _run():
            import concurrent.futures
            t0 = time.time()
            results = {}

            def _holder_count():
                try: return ("股东户数历史", ak.stock_circulate_stock_holder(symbol=code))
                except Exception as e: return ("股东户数历史", None)

            def _top_holders():
                try: return ("十大股东历史", ak.stock_main_stock_holder(stock=code))
                except Exception as e: return ("十大股东历史", None)

            def _fund_holdings():
                try: return ("基金持仓明细", ak.stock_fund_stock_holder(symbol=code))
                except Exception as e: return ("基金持仓明细", None)

            def _hsgt():
                try: return ("北向持股历史", ak.stock_hsgt_individual_em(symbol=code))
                except Exception as e: return ("北向持股历史", None)

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = {
                    pool.submit(_holder_count): "股东户数",
                    pool.submit(_top_holders): "十大股东",
                    pool.submit(_fund_holdings): "基金持仓",
                    pool.submit(_hsgt): "北向持股",
                }
                for fut, key in futures.items():
                    try:
                        label, df = fut.result(timeout=30)
                        results[key] = (label, df)
                    except Exception:
                        results[key] = (fut.exception(), None)

            dt = time.time() - t0
            if self._inst_buy_dlg and self._inst_buy_dlg.winfo_exists():
                self._inst_buy_dlg.after(0, lambda: self._render_ak_detail(code, name, results, dt))
        threading.Thread(target=_run, daemon=True).start()

    def _render_ak_detail(self, code, name, results, dt=0):
        """渲染 AKShare 详情到右栏两个 tab"""
        import pandas as pd

        def _render_tab(tab, title_str, dataframes):
            for w in tab.winfo_children(): w.destroy()
            tk.Label(tab, text=title_str, font=("", 12, "bold")).pack(anchor="w", padx=4, pady=4)

            nb = ttk.Notebook(tab)
            nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

            for label, df in dataframes:
                frame = ttk.Frame(nb)
                nb.add(frame, text=label[:25] + ("..." if len(label) > 25 else ""))

                if df is None or len(df) == 0:
                    ttk.Label(frame, text="📭 AKShare 接口暂不可用", foreground="gray").pack(pady=20)
                    continue

                cols = list(df.columns)
                items = df.head(300).values.tolist()  # 最多 300 行
                tree_cols = [str(c) for c in cols]
                tv = ttk.Treeview(frame, columns=tree_cols, show="headings",
                                  height=min(15, len(items)))

                def _cw(idx, _cols=cols, _items=items):
                    mc = str(_cols[idx] if idx < len(_cols) else "")
                    for row in _items:
                        if idx < len(row):
                            cell = str(row[idx])[:80] if row[idx] else ""
                            if len(cell) > len(mc): mc = cell
                    w = sum(14 if ord(ch) > 127 else 8 for ch in mc)
                    return max(50, min(300, w + 14))

                for h, w in zip(tree_cols, [_cw(i) for i in range(len(tree_cols))]):
                    tv.heading(h, text=h)
                    tv.column(h, width=w, anchor="w", minwidth=45)
                for row in items:
                    vals = [str(v)[:100] if v else "" for v in row[:len(tree_cols)]]
                    tv.insert("", tk.END, values=vals)

                vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tv.yview)
                hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tv.xview)
                tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
                tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
                vsb.pack(side=tk.RIGHT, fill=tk.Y)
                hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # 🏒 机构持仓历史 tab
        hold_tables = []
        if "股东户数" in results and results["股东户数"][1] is not None:
            hold_tables.append(results["股东户数"])
        if "十大股东" in results and results["十大股东"][1] is not None:
            hold_tables.append(results["十大股东"])
        _render_tab(self._inst_holding_tab, f"🏒 {name}({code}) 机构/股东 (AKShare免费)", hold_tables)

        # 📰 资讯研报 tab (用 AKShare 北向 + 基金持仓)
        news_tables = []
        if "北向持股" in results and results["北向持股"][1] is not None:
            news_tables.append(results["北向持股"])
        if "基金持仓" in results and results["基金持仓"][1] is not None:
            news_tables.append(results["基金持仓"])
        _render_tab(self._inst_news_tab, f"📰 {name} AKShare 免费数据 ({dt:.1f}s)", news_tables)
