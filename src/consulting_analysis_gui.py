"""
consulting_analysis_gui.py
咨询分析与问财条件选股（坐电梯）界面模块

提供：
- ConsultingAnalysisApp: 多维度咨询分析工作台（麦肯锡/波士顿/埃森哲等框架）
- ElevatorDialog: 问财条件选股对话框
"""

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

ANALYSIS_DIMENSIONS = {
    "咨询分析": {
        "麦肯锡 7S": "战略、结构、系统、风格、人员、技能、价值观",
        "波士顿矩阵": "明星、现金牛、问号、瘦狗产品分类",
        "埃森哲价值地图": "价值创造和价值获取路径",
        "波特五力": "竞争环境分析：供应商、买方、替代品、潜在进入者、同业竞争",
        "PESTEL": "政治、经济、社会、技术、环境、法律分析",
        "SWOT": "优势、劣势、机会、威胁分析",
        "安索夫矩阵": "市场-产品增长策略",
        "GE 九宫格": "行业吸引力与竞争地位评估",
        "3C 模型": "公司、客户、竞争对手分析",
        "价值链分析": "企业内部价值创造活动分析",
        "综合推断 (咨询)": "整合多个咨询框架的综合分析",
        "平衡计分卡": "财务、客户、内部流程、学习成长四个维度",
        "OKR 对齐": "目标与关键结果对齐分析",
    },
    "投资": {
        "股票": "股票投资分析，包括个股选择、行业分析、技术面、基本面等",
        "房地产": "房地产投资分析，包括住宅、商业地产、REITs等投资机会",
        "债券": "债券投资分析，包括国债、企业债、可转债等固定收益产品",
        "数字货币": "数字货币投资分析，包括比特币、以太坊等加密货币",
        "基金": "基金投资分析，包括股票基金、债券基金、混合基金、ETF等",
        "期货": "期货投资分析，包括商品期货、金融期货等衍生品",
        "外汇": "外汇投资分析，包括主要货币对、汇率走势等",
        "黄金": "黄金投资分析，包括实物黄金、黄金ETF、黄金期货等",
        "大宗商品": "大宗商品投资分析，包括原油、铜、农产品等",
        "另类投资": "另类投资分析，包括私募股权、对冲基金、艺术品等",
    },
    "系统": {
        "价值投资": "本杰明·格雷厄姆和沃伦·巴菲特的价值投资体系",
        "海龟交易法则": "理查德·丹尼斯的海龟交易系统，基于趋势跟踪、仓位管理",
        "量化投资": "基于数学模型和算法的量化投资策略",
        "技术分析": "基于价格和成交量图表的技术分析方法",
        "基本面分析": "基于公司财务数据、行业状况、宏观经济的基本面分析",
        "成长投资": "菲利普·费雪的成长投资策略，关注高成长性公司",
        "动量投资": "基于价格动量和相对强度的动量投资策略",
        "均值回归": "基于价格偏离均值的均值回归投资策略",
        "因子投资": "基于多因子模型的因子投资策略",
        "资产配置": "现代投资组合理论，包括马科维茨模型、风险平价等",
    },
    "赌博": {
        "凯利公式": "计算最优投注比例，基于胜率和赔率",
        "概率计算": "计算各种概率场景，包括胜率、赔率、期望值等",
        "风险收益比": "计算风险收益比，评估投资机会的风险调整后收益",
        "仓位管理": "基于概率和风险的资金管理策略",
        "期望值分析": "计算投资的期望值，评估长期收益预期",
        "最大回撤": "分析最大回撤风险，评估资金管理的安全性",
        "夏普比率": "计算风险调整后的收益指标，评估投资效率",
        "蒙特卡洛模拟": "使用蒙特卡洛方法模拟投资结果，评估概率分布",
        "VaR风险值": "计算在险价值，评估投资组合的风险敞口",
        "压力测试": "进行压力测试，评估极端情况下的投资表现",
    },
    "安全": {
        "同花顺情绪指数": "分析同花顺情绪指数883404的日K、60分钟周期、15分钟周期的情绪判断",
        "信用风险": "评估交易对手的信用风险，包括公司财务状况、债务水平",
        "市场风险": "评估市场波动带来的风险，包括系统性风险、黑天鹅事件",
        "流动性风险": "评估资产变现的难易程度，包括交易量、买卖价差",
        "操作风险": "评估操作失误带来的风险，包括下单错误、系统故障",
        "政策风险": "评估政策变化带来的风险，包括监管政策、税收政策",
        "汇率风险": "评估汇率波动带来的风险，包括外汇敞口、汇率对冲",
        "集中度风险": "评估投资过于集中带来的风险",
        "杠杆风险": "评估使用杠杆带来的风险，包括融资融券、期货杠杆",
        "估值风险": "评估资产估值过高带来的风险，包括PE/PB过高、泡沫风险",
    },
    "流动性": {
        "市场流动性": "评估标的物的市场流动性，包括成交量、换手率、买卖盘深度",
        "跌停板检查": "检查是否处于跌停板状态，跌停板无法买入，缺乏流动性",
        "涨停板检查": "检查是否处于涨停板状态，涨停板难以买入，流动性受限",
        "停牌检查": "检查是否处于停牌状态，停牌期间无法交易，无流动性",
        "ST股票检查": "检查是否为ST股票，ST股票交易受限，流动性较差",
        "成交量分析": "分析成交量变化，评估市场参与度和流动性状况",
        "买卖价差": "分析买卖价差，评估交易成本和流动性质量",
        "大宗交易": "分析大宗交易情况，评估机构参与度和市场深度",
        "限售解禁": "分析限售股解禁情况，评估潜在抛压和流动性冲击",
        "不当投资检查": "检查不当投资情况，如跌停板、停牌、ST等流动性陷阱",
    },
    "利润": {
        "趋势分析": "分析价格趋势，包括月线MACD双金叉、60分钟短线非死叉、15分钟多头排列",
        "月线MACD双金叉": "月线级别MACD双金叉，确认长期上涨趋势",
        "60分钟非死叉": "60分钟级别MACD未死叉，确认中期上涨趋势",
        "15分钟多头排列": "15分钟级别均线多头排列，确认短期上涨趋势",
        "技术指标": "综合分析各种技术指标，包括MACD、KDJ、RSI、BOLL等",
        "量价关系": "分析成交量与价格的关系，确认上涨的有效性",
        "支撑阻力": "分析关键支撑位和阻力位，确定买入和卖出时机",
        "形态识别": "识别K线形态，包括头肩底、双底、三角形等反转或持续形态",
        "资金流向": "分析主力资金流向，确认资金是否流入",
        "盈利预期": "评估盈利预期，包括目标价位、止损价位、风险收益比",
    },
}


class ConsultingAnalysisApp:
    """咨询分析工作台 - 多维度AI分析界面"""

    def __init__(self, parent, ai_call_func=None, ai_config_manager=None):
        self.parent = parent
        self.ai_call_func = ai_call_func
        self.ai_config_manager = ai_config_manager
        self.checkbox_vars = {}

        parent.title("咨询分析工作台 - 多维度智能分析")
        parent.geometry("1440x860")
        try:
            parent.state("zoomed")
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        header = ttk.Label(
            self.parent,
            text="选择分析维度（可多选），选中的维度将作为分析条件进行AI综合分析",
            anchor="center",
            font=("Microsoft YaHei", 13, "bold"),
        )
        header.pack(fill=tk.X, padx=12, pady=(10, 6))

        # Use PanedWindow for 50/50 resizable split
        body = ttk.PanedWindow(self.parent, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))

        # ===== Left: condition input (50%) =====
        left_frame = ttk.Frame(body)
        body.add(left_frame, weight=1)

        left_inner = ttk.LabelFrame(left_frame, text="分析条件 / 问题描述", padding=6)
        left_inner.pack(fill=tk.BOTH, expand=True)

        ttk.Label(left_inner, text="请输入分析问题（如：分析贵州茅台的投资价值）：",
                  font=("Microsoft YaHei", 10)).pack(anchor=tk.W)

        # Toolbar for text operations
        text_toolbar = ttk.Frame(left_inner)
        text_toolbar.pack(fill=tk.X, pady=(2, 3))
        ttk.Button(text_toolbar, text="📋 粘贴", width=7, command=self._paste_from_clipboard).pack(side=tk.LEFT, padx=1)
        ttk.Button(text_toolbar, text="✂️ 剪切", width=7, command=self._cut_selection).pack(side=tk.LEFT, padx=1)
        ttk.Button(text_toolbar, text="📑 复制", width=7, command=self._copy_selection).pack(side=tk.LEFT, padx=1)
        ttk.Button(text_toolbar, text="🗑️ 清空", width=7, command=self._clear_condition).pack(side=tk.LEFT, padx=1)
        ttk.Button(text_toolbar, text="全选", width=5, command=self._select_all_text).pack(side=tk.LEFT, padx=1)
        ttk.Label(text_toolbar, text="   (Cmd+C/V/X)",
                  foreground="#999999", font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)

        self.condition_text = tk.Text(
            left_inner, wrap=tk.WORD, height=12, font=("Microsoft YaHei", 11),
            undo=True, maxundo=50,
            insertbackground="#333333",
            selectbackground="#4a90d9",
            selectforeground="white",
        )
        yscroll = ttk.Scrollbar(left_inner, orient="vertical", command=self.condition_text.yview)
        self.condition_text.configure(yscrollcommand=yscroll.set)
        self.condition_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(2, 4))
        yscroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(2, 4))

        self._bind_clipboard_events(self.condition_text)

        # Quick questions - compact display below
        quick_frame = ttk.LabelFrame(left_inner, text="快捷问题（点击插入）", padding=3)
        quick_frame.pack(fill=tk.X, pady=(0, 4))

        quick_questions = [
            "分析贵州茅台的投资价值",
            "当前A股市场整体趋势判断",
            "新能源板块龙头股分析",
            "分析比亚迪的竞争优势",
            "白酒行业的前景如何",
            "用波特五力分析宁德时代",
            "用麦肯锡7S分析招商银行",
            "当前市场情绪如何，是否可加仓",
        ]

        q_wrap = ttk.Frame(quick_frame)
        q_wrap.pack(fill=tk.X)
        for i, q in enumerate(quick_questions):
            ttk.Button(q_wrap, text=q,
                       command=lambda text=q: self.condition_text.delete("1.0", tk.END) or self.condition_text.insert("1.0", text),
                       width=20).grid(row=i // 4, column=i % 4, padx=2, pady=1, sticky="we")
        for c in range(4):
            q_wrap.columnconfigure(c, weight=1)

        # ===== Right: AI result (50%) =====
        right_frame = ttk.Frame(body)
        body.add(right_frame, weight=1)

        right_inner = ttk.LabelFrame(right_frame, text="AI 分析结果（可选中复制/保存）", padding=6)
        right_inner.pack(fill=tk.BOTH, expand=True)

        result_toolbar = ttk.Frame(right_inner)
        result_toolbar.pack(fill=tk.X, pady=(0, 3))
        ttk.Button(result_toolbar, text="📋 复制全部", width=9, command=self._copy_result_all).pack(side=tk.LEFT, padx=1)
        ttk.Button(result_toolbar, text="📑 复制选中", width=9, command=self._copy_result_selection).pack(side=tk.LEFT, padx=1)
        ttk.Button(result_toolbar, text="📋 粘贴", width=7, command=self._paste_result).pack(side=tk.LEFT, padx=1)
        ttk.Button(result_toolbar, text="✂️ 剪切", width=7, command=self._cut_result).pack(side=tk.LEFT, padx=1)
        ttk.Button(result_toolbar, text="💾 保存", width=7, command=self._save_result_to_file).pack(side=tk.LEFT, padx=1)
        ttk.Button(result_toolbar, text="🖼️ 长图", width=7, command=self._result_to_long_image).pack(side=tk.LEFT, padx=1)
        self._result_lock_btn = ttk.Button(result_toolbar, text="🔓 解锁编辑", width=10, command=self._toggle_result_lock)
        self._result_lock_btn.pack(side=tk.LEFT, padx=1)
        ttk.Button(result_toolbar, text="🗑️ 清空", width=7, command=self._clear_result).pack(side=tk.LEFT, padx=1)

        self.result_text = tk.Text(
            right_inner, wrap=tk.WORD, font=("Microsoft YaHei", 11),
            state=tk.NORMAL, bg="#FAFAFA",
            selectbackground="#4a90d9", selectforeground="white",
            undo=True, maxundo=20,
        )
        self._result_locked = True
        self._bind_result_key_events()

        ryscroll = ttk.Scrollbar(right_inner, orient="vertical", command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=ryscroll.set)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ryscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_result_clipboard_events()

        # Bottom: dimension selection tabs
        bottom_frame = ttk.LabelFrame(self.parent, text="分析维度选择（勾选后点击「开始AI分析」）", padding=6)
        bottom_frame.pack(fill=tk.BOTH, expand=False, padx=12, pady=(0, 8))

        notebook = ttk.Notebook(bottom_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        for category, options in ANALYSIS_DIMENSIONS.items():
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=f"  {category}  ")

            canvas = tk.Canvas(tab, highlightthickness=0)
            vsb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            inner = ttk.Frame(canvas)

            inner.bind(
                "<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),
            )
            canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=vsb.set)

            def _wheel(event, c=canvas):
                c.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind("<MouseWheel>", _wheel)
            inner.bind("<MouseWheel>", _wheel)

            canvas.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            row = 0
            col = 0
            max_cols = 3
            for opt_name, opt_desc in options.items():
                var = tk.BooleanVar()
                self.checkbox_vars[opt_name] = var

                if opt_name == "同花顺情绪指数":
                    var.trace_add("write", lambda *args: self._on_sentiment_toggle())

                cb_frame = ttk.Frame(inner)
                cb_frame.grid(row=row, column=col, sticky="w", padx=4, pady=3)

                cb = tk.Checkbutton(
                    cb_frame, text=opt_name, variable=var,
                    font=("Microsoft YaHei", 10, "bold"),
                    anchor="w"
                )
                cb.pack(anchor=tk.W)

                ttk.Label(cb_frame, text=opt_desc,
                          foreground="#666666",
                          font=("Microsoft YaHei", 8),
                          wraplength=320, justify=tk.LEFT).pack(anchor=tk.W, padx=(20, 0))

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

        # Action buttons
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        ttk.Button(btn_frame, text="清空条件", command=self._clear_condition).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="全选所有维度", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消全选", command=self._deselect_all).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="开始 AI 分析", command=self._run_analysis).pack(side=tk.RIGHT, padx=5)

        self.status_var = tk.StringVar(value="就绪 - 请选择分析维度并输入问题")
        ttk.Label(btn_frame, textvariable=self.status_var,
                  font=("Microsoft YaHei", 10),
                  foreground="#555555").pack(side=tk.RIGHT, padx=15)

    def _on_sentiment_toggle(self):
        """同花顺情绪指数特殊处理"""
        if self.checkbox_vars.get("同花顺情绪指数", tk.BooleanVar()).get():
            self.condition_text.delete("1.0", tk.END)
            self.condition_text.insert("1.0",
                "同花顺情绪指数883404的日K，60分钟周期，15分钟周期的情绪判断如何，情绪指数相关的重要指标和分析有哪些，现在如何。")

    def _clear_condition(self):
        self.condition_text.delete("1.0", tk.END)

    def _select_all(self):
        for var in self.checkbox_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self.checkbox_vars.values():
            var.set(False)

    def _bind_clipboard_events(self, text_widget):
        """为文本控件绑定剪贴板事件（支持 macOS Cmd+C/V/X 与 Win/Linux Ctrl+C/V/X）"""
        text_widget.bind("<Command-c>", lambda e: self._safe_copy(text_widget))
        text_widget.bind("<Command-v>", lambda e: self._safe_paste(text_widget))
        text_widget.bind("<Command-x>", lambda e: self._safe_cut(text_widget))
        text_widget.bind("<Command-a>", lambda e: self._safe_select_all(text_widget))
        text_widget.bind("<Control-c>", lambda e: self._safe_copy(text_widget))
        text_widget.bind("<Control-v>", lambda e: self._safe_paste(text_widget))
        text_widget.bind("<Control-x>", lambda e: self._safe_cut(text_widget))
        text_widget.bind("<Control-a>", lambda e: self._safe_select_all(text_widget))
        text_widget.bind("<Button-3>", lambda e: self._show_context_menu(text_widget, e))

    def _bind_result_clipboard_events(self):
        """为结果文本框绑定剪贴板事件（支持复制/粘贴/剪切）"""
        self.result_text.bind("<Command-c>", lambda e: self._safe_copy(self.result_text))
        self.result_text.bind("<Command-v>", lambda e: self._safe_paste(self.result_text))
        self.result_text.bind("<Command-x>", lambda e: self._safe_cut(self.result_text))
        self.result_text.bind("<Command-a>", lambda e: self._safe_select_all(self.result_text))
        self.result_text.bind("<Control-c>", lambda e: self._safe_copy(self.result_text))
        self.result_text.bind("<Control-v>", lambda e: self._safe_paste(self.result_text))
        self.result_text.bind("<Control-x>", lambda e: self._safe_cut(self.result_text))
        self.result_text.bind("<Control-a>", lambda e: self._safe_select_all(self.result_text))
        self.result_text.bind("<Button-3>", lambda e: self._show_result_context_menu(e))

    def _bind_result_key_events(self):
        """结果文本框默认锁定编辑（防止误改AI结果），可通过按钮解锁"""
        self.result_text.bind("<Key>", self._on_result_key)

    def _on_result_key(self, event):
        if self._result_locked:
            if event.keysym in ("c", "C", "a", "A", "v", "V", "x", "X", "z", "Z",
                                "Left", "Right", "Up", "Down", "Home", "End",
                                "BackSpace", "Delete"):
                return None
            return "break"
        return None

    def _toggle_result_lock(self):
        self._result_locked = not self._result_locked
        if self._result_locked:
            self._result_lock_btn.config(text="🔓 解锁编辑")
        else:
            self._result_lock_btn.config(text="🔒 锁定编辑")

    def _show_result_context_menu(self, event):
        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(label="复制 (Cmd+C)", command=lambda: self._safe_copy(self.result_text))
        menu.add_command(label="粘贴 (Cmd+V)", command=lambda: self._safe_paste(self.result_text))
        menu.add_command(label="剪切 (Cmd+X)", command=lambda: self._safe_cut(self.result_text))
        menu.add_separator()
        menu.add_command(label="全选 (Cmd+A)", command=lambda: self._safe_select_all(self.result_text))
        menu.add_command(label="保存到文件", command=self._save_result_to_file)
        menu.add_separator()
        menu.add_command(label="锁定/解锁编辑", command=self._toggle_result_lock)
        menu.tk_popup(event.x_root, event.y_root)

    def _safe_copy(self, widget):
        try:
            text = widget.get("sel.first", "sel.last")
        except Exception:
            text = ""
        if not text:
            try:
                text = widget.get("1.0", tk.END).strip()
            except Exception:
                text = ""
        if text:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(text)
        return "break"

    def _safe_paste(self, widget):
        try:
            clip = self.parent.clipboard_get()
            try:
                widget.delete("sel.first", "sel.last")
            except Exception:
                pass
            widget.insert(tk.INSERT, clip)
            widget.see(tk.INSERT)
        except Exception:
            pass
        return "break"

    def _safe_cut(self, widget):
        try:
            text = widget.get("sel.first", "sel.last")
            if text:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(text)
                widget.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def _safe_select_all(self, widget):
        widget.tag_add("sel", "1.0", tk.END)
        widget.mark_set(tk.INSERT, "1.0")
        widget.see(tk.INSERT)
        return "break"

    def _show_context_menu(self, widget, event):
        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(label="复制 (Cmd+C)", command=lambda: self._safe_copy(widget))
        if widget is self.condition_text:
            menu.add_command(label="粘贴 (Cmd+V)", command=lambda: self._safe_paste(widget))
            menu.add_command(label="剪切 (Cmd+X)", command=lambda: self._safe_cut(widget))
            menu.add_separator()
            menu.add_command(label="全选 (Cmd+A)", command=lambda: self._safe_select_all(widget))
            menu.add_command(label="清空", command=lambda: widget.delete("1.0", tk.END))
        else:
            menu.add_separator()
            menu.add_command(label="全选", command=lambda: self._safe_select_all(widget))
        menu.tk_popup(event.x_root, event.y_root)

    def _paste_from_clipboard(self):
        try:
            self._safe_paste(self.condition_text)
            self.condition_text.focus_set()
        except Exception:
            messagebox.showinfo("提示", "剪贴板为空或无法读取", parent=self.parent)

    def _cut_selection(self):
        self._safe_cut(self.condition_text)

    def _copy_selection(self):
        self._safe_copy(self.condition_text)

    def _select_all_text(self):
        self.condition_text.tag_add("sel", "1.0", tk.END)
        self.condition_text.focus_set()

    def _copy_result_all(self):
        try:
            self._result_locked = False
            text = self.result_text.get("1.0", tk.END).strip()
            self._result_locked = True
            if text:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(text)
                messagebox.showinfo("成功", "分析结果已复制到剪贴板", parent=self.parent)
        except Exception:
            messagebox.showerror("错误", "复制失败", parent=self.parent)

    def _copy_result_selection(self):
        try:
            self._result_locked = False
            if self.result_text.tag_ranges("sel"):
                selected = self.result_text.get("sel.first", "sel.last")
                self.parent.clipboard_clear()
                self.parent.clipboard_append(selected)
            else:
                messagebox.showinfo("提示", "请先选中要复制的文本", parent=self.parent)
            self._result_locked = True
        except Exception:
            self._result_locked = True
            messagebox.showerror("错误", "复制失败", parent=self.parent)

    def _paste_result(self):
        self._result_locked = False
        self._safe_paste(self.result_text)
        self._result_locked = True

    def _cut_result(self):
        self._result_locked = False
        self._safe_cut(self.result_text)
        self._result_locked = True

    def _save_result_to_file(self):
        try:
            from tkinter import filedialog
            self._result_locked = False
            text = self.result_text.get("1.0", tk.END).strip()
            self._result_locked = True
            if not text:
                messagebox.showinfo("提示", "结果为空，无需保存", parent=self.parent)
                return

            filepath = filedialog.asksaveasfilename(
                parent=self.parent,
                title="保存分析结果",
                defaultextension=".txt",
                filetypes=[
                    ("文本文件", "*.txt"),
                    ("Markdown文件", "*.md"),
                    ("所有文件", "*.*"),
                ],
                initialfile=f"咨询分析结果_{self._get_timestamp()}.txt",
            )
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text)
                messagebox.showinfo("成功", f"分析结果已保存到：\n{filepath}", parent=self.parent)
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}", parent=self.parent)

    def _get_timestamp(self):
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _clear_result(self):
        self._result_locked = False
        self.result_text.delete("1.0", tk.END)
        self._result_locked = True

    def _result_to_long_image(self):
        """将AI分析结果生成为长图"""
        try:
            self._result_locked = False
            text = self.result_text.get("1.0", tk.END).strip()
            self._result_locked = True

            if not text:
                messagebox.showinfo("提示", "结果为空，无法生成图片", parent=self.parent)
                return

            from tkinter import filedialog

            from PIL import Image, ImageDraw, ImageFont

            # 参数配置
            img_width = 1080
            padding = 60
            content_width = img_width - padding * 2
            font_size = 26
            line_spacing = 10
            title_font_size = 36
            bg_color = (250, 250, 250)
            text_color = (51, 51, 51)
            header_bg = (74, 144, 217)
            header_color = (255, 255, 255)
            separator_color = (220, 220, 220)

            # 尝试加载中文字体
            font_paths = [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/Library/Fonts/Songti.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
            ]
            font = None
            title_font = None
            for fp in font_paths:
                try:
                    font = ImageFont.truetype(fp, font_size)
                    title_font = ImageFont.truetype(fp, title_font_size)
                    break
                except Exception:
                    continue
            if font is None:
                font = ImageFont.load_default()
                title_font = ImageFont.load_default()

            draw_temp = ImageDraw.Draw(Image.new("RGB", (1, 1)))

            # 文本按行换行处理
            wrapped_lines = []
            for raw_line in text.split("\n"):
                if not raw_line.strip():
                    wrapped_lines.append("")
                    continue
                # 按像素宽度换行
                current = ""
                for char in raw_line:
                    test = current + char
                    try:
                        bbox = draw_temp.textbbox((0, 0), test, font=font)
                        w = bbox[2] - bbox[0]
                    except Exception:
                        w = len(test) * font_size
                    if w > content_width and current:
                        wrapped_lines.append(current)
                        current = char
                    else:
                        current = test
                if current:
                    wrapped_lines.append(current)

            # 计算图片高度
            line_height = font_size + line_spacing
            header_height = 80
            footer_height = 50
            img_height = header_height + padding + len(wrapped_lines) * line_height + padding + footer_height

            # 创建图片
            img = Image.new("RGB", (img_width, img_height), bg_color)
            draw = ImageDraw.Draw(img)

            # 绘制顶部标题栏
            draw.rectangle([0, 0, img_width, header_height], fill=header_bg)
            title_text = "📊 AI 咨询分析结果"
            try:
                bbox = draw.textbbox((0, 0), title_text, font=title_font)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(title_text) * title_font_size
            tx = (img_width - tw) // 2
            draw.text((tx, 22), title_text, fill=header_color, font=title_font)

            # 绘制分隔线
            draw.line([(padding, header_height), (img_width - padding, header_height)],
                      fill=separator_color, width=2)

            # 绘制正文
            y = header_height + padding
            for i, line in enumerate(wrapped_lines):
                # 标题行（===分隔线）用浅灰色
                if line.strip().startswith("="):
                    draw.line([(padding, y + font_size // 2), (img_width - padding, y + font_size // 2)],
                              fill=separator_color, width=1)
                elif line.strip().startswith("📊") or line.strip().startswith("🔸"):
                    draw.text((padding, y), line, fill=(0, 102, 153), font=font)
                elif line.strip().startswith("⏳") or line.strip().startswith("⚠️"):
                    draw.text((padding, y), line, fill=(204, 102, 0), font=font)
                else:
                    draw.text((padding, y), line, fill=text_color, font=font)
                y += line_height

            # 绘制底部信息
            from datetime import datetime
            footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            try:
                bbox = draw.textbbox((0, 0), footer_text, font=font)
                fw = bbox[2] - bbox[0]
            except Exception:
                fw = len(footer_text) * font_size
            fx = (img_width - fw) // 2
            draw.text((fx, img_height - 40), footer_text, fill=(153, 153, 153), font=font)

            # 保存
            filepath = filedialog.asksaveasfilename(
                parent=self.parent,
                title="保存长图",
                defaultextension=".png",
                filetypes=[("PNG图片", "*.png"), ("JPEG图片", "*.jpg"), ("所有文件", "*.*")],
                initialfile=f"咨询分析长图_{self._get_timestamp()}.png",
            )
            if filepath:
                img.save(filepath, "PNG")
                # 尝试复制图片到剪贴板（macOS）
                clip_copied = False
                try:
                    import subprocess
                    script = f'set the clipboard to (read POSIX file "{filepath}" as «class PNGf»)'
                    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
                    clip_copied = True
                except Exception:
                    pass
                msg = f"长图已保存到：\n{filepath}"
                if clip_copied:
                    msg += "\n\n✅ 已复制到剪贴板，可直接粘贴到微信/QQ等"
                messagebox.showinfo("成功", msg, parent=self.parent)

        except Exception as e:
            messagebox.showerror("错误", f"生成长图失败: {e}", parent=self.parent)

    def _run_analysis(self):
        selected = [name for name, var in self.checkbox_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个分析维度")
            return

        problem = self.condition_text.get("1.0", tk.END).strip()
        if not problem:
            messagebox.showwarning("提示", "请输入分析问题")
            return

        self.status_var.set("AI 分析中，请稍候...")
        self._result_locked = False
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, "⏳ AI 分析进行中，请稍候...\n")
        self._result_locked = True
        self.parent.update()

        threading.Thread(
            target=self._do_ai_analysis,
            args=(selected, problem),
            daemon=True,
        ).start()

    def _do_ai_analysis(self, selected, problem):
        try:
            dimensions_text = "\n".join([f"  • {d}" for d in selected])
            prompt = f"""请基于以下分析维度，对以下问题进行综合分析：

分析维度：
{dimensions_text}

分析问题：
{problem}

请提供：
1. 各维度下的关键分析点
2. 维度间的关联和影响
3. 综合判断和建议
4. 风险提示和注意事项"""

            system_prompt = "你是一位资深的多维度投资分析专家，精通麦肯锡、波士顿、埃森哲等咨询框架，能够从多个角度综合分析投资问题。请用中文回答，分析要专业、深入、有建设性。"

            if self.ai_call_func:
                ai_result = self.ai_call_func(prompt=prompt, system_prompt=system_prompt)
                if not ai_result or ai_result.startswith("错误"):
                    ai_result = f"AI 服务暂时不可用。\n\n错误信息：{ai_result}\n\n请检查 AI 配置是否正确。"
            else:
                ai_result = (
                    "⚠️ AI 功能未配置。\n\n"
                    "请在主界面的「系统」→「AI 设置」中配置 AI 提供商后重试。\n\n"
                    "您也可以使用以下快捷功能：\n"
                    "  • 查看持仓详情\n"
                    "  • 查看技术指标分析\n"
                    "  • 使用问财条件选股（坐电梯）"
                )
        except Exception as e:
            ai_result = f"AI 分析失败: {e!s}"

        def update_ui():
            self._result_locked = False
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, "📊 综合分析结果\n\n")
            self.result_text.insert(tk.END, "=" * 60 + "\n\n")
            self.result_text.insert(tk.END, f"🔸 分析维度：{', '.join(selected)}\n\n")
            self.result_text.insert(tk.END, "=" * 60 + "\n\n")
            self.result_text.insert(tk.END, ai_result)
            self._result_locked = True
            self.status_var.set("✅ 分析完成")

        if hasattr(self.parent, "winfo_exists") and self.parent.winfo_exists():
            self.parent.after(0, update_ui)


class ElevatorDialog:
    """问财条件选股对话框（坐电梯）"""

    def __init__(self, app):
        self.app = app
        self.master = app.master

        self.win = tk.Toplevel(self.master)
        self.win.title("条件选股（坐电梯）")
        self.win.geometry("1650x950")
        self.win.transient(self.master)
        self.win.resizable(True, True)

        self._setup_ui()

    def _setup_ui(self):
        paned_main = ttk.PanedWindow(self.win, orient=tk.HORIZONTAL)
        paned_main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = ttk.LabelFrame(paned_main, text="查询条件", width=420)
        right_frame = ttk.LabelFrame(paned_main, text="查询结果（双击行查看详情）")
        paned_main.add(left_frame, weight=3)
        paned_main.add(right_frame, weight=5)

        try:
            paned_main.paneconfigure(left_frame, minsize=300)
            paned_main.paneconfigure(right_frame, minsize=400)
            # 强制把 splitter 放到 40% 位置（左40% 右60%），防止被拖到角落
            self.win.update_idletasks()
            try:
                w = paned_main.winfo_width()
                if w > 800:
                    paned_main.sashpos(0, int(w * 0.42))
            except Exception:
                pass
        except Exception:
            pass

        ttk.Label(left_frame, text="输入查询条件:", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))

        self.query_text = scrolledtext.ScrolledText(left_frame, height=3, width=45, wrap=tk.WORD, font=("Microsoft YaHei", 12))
        self.query_text.pack(fill=tk.X, padx=10, pady=(0, 6))

        default_query = "周线周期的wr2大于80，周线周期的d小于30且周线周期的bias3小于-10，非st，周线周期的diff大于0，基本面从好到坏"
        self.query_text.insert(tk.END, default_query)

        preset_frame = ttk.LabelFrame(left_frame, text="预设查询条件")
        preset_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        preset_queries = [
            ("技术指标组合", "周线周期的wr2大于80，周线周期的d小于30且周线周期的bias3小于-10，非st，周线周期的diff大于0，基本面从好到坏"),
            ("涨停股票", "今日涨停股票"),
            ("成交量最大", "今日成交量最大的前20只股票"),
            ("北向资金", "北向资金净流入前20只股票"),
            ("涨幅最大", "今日涨幅最大的股票"),
            ("跌幅最大", "今日跌幅最大的股票"),
            ("低位放量", "非st，非退市，所属行业龙头，近5日放量上涨，今日收盘价接近60日线"),
            ("趋势突破", "非st，20日均线>60日均线>120日均线，今日放量突破前高，MACD金叉"),
            ("反转模型", "近10日跌幅>15%，但放量止跌，今日收盘价站上5日线且KDJ金叉"),
            ("60分上穿60日", "非st，60分钟周期下股价首次向上突破60分钟MA60均线，突破当日该60分钟周期成交量较前10个60分钟周期平均成交量放大50%以上"),
        ]

        row1_frame = ttk.Frame(preset_frame)
        row1_frame.pack(fill=tk.X, padx=5, pady=2)
        row2_frame = ttk.Frame(preset_frame)
        row2_frame.pack(fill=tk.X, padx=5, pady=2)

        for i, (name, query) in enumerate(preset_queries):
            target_row = row1_frame if i < 5 else row2_frame
            btn = ttk.Button(target_row, text=name,
                             command=lambda q=query: self.query_text.delete("1.0", tk.END) or self.query_text.insert("1.0", q))
            btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        ttk.Button(left_frame, text="查询", command=self._do_query).pack(fill=tk.X, padx=10, pady=10)

        result_frame = ttk.Frame(right_frame)
        result_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("序号", "代码", "名称", "最新价", "涨跌幅", "成交额", "振幅")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=25)

        col_widths = {"序号": 50, "代码": 80, "名称": 100, "最新价": 90, "涨跌幅": 80, "成交额": 80, "振幅": 80}
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)

        status_frame = ttk.Frame(right_frame)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var, font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

    def _do_query(self):
        query = self.query_text.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("提示", "请输入查询条件", parent=self.win)
            return

        self.status_var.set("正在查询...")
        self.win.update()

        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            stocks = self._mock_query(query)
            for i, s in enumerate(stocks, 1):
                self.tree.insert("", tk.END, values=(i, s["code"], s["name"], s["price"], s["change"], s["amount"], s["amplitude"]))
            self.status_var.set(f"查询完成，共找到 {len(stocks)} 只股票")
        except Exception as e:
            self.status_var.set(f"查询失败: {e!s}")
            messagebox.showerror("错误", f"查询失败: {e!s}", parent=self.win)

    def _mock_query(self, query):
        return [
            {"code": "600519", "name": "贵州茅台", "price": "1680.00", "change": "+1.25%", "amount": "8.5亿", "amplitude": "2.15%"},
            {"code": "000858", "name": "五粮液", "price": "152.30", "change": "+0.85%", "amount": "5.2亿", "amplitude": "1.85%"},
            {"code": "601318", "name": "中国平安", "price": "45.68", "change": "-0.35%", "amount": "3.8亿", "amplitude": "1.25%"},
            {"code": "300750", "name": "宁德时代", "price": "215.50", "change": "+2.35%", "amount": "12.5亿", "amplitude": "3.25%"},
            {"code": "002594", "name": "比亚迪", "price": "238.80", "change": "+1.65%", "amount": "9.8亿", "amplitude": "2.85%"},
        ]

    def _on_double_click(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        values = self.tree.item(item, "values")
        if values and len(values) >= 2:
            stock_code = values[1]
            stock_name = values[2] if len(values) > 2 else ""
            messagebox.showinfo("股票详情",
                                f"股票: {stock_name} ({stock_code})\n\n请在主界面输入框中输入代码查看日K线图。",
                                parent=self.win)
